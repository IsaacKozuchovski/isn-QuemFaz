import json
import mimetypes
import subprocess
from pathlib import Path

import pulumi
import pulumi_aws as aws

stack = pulumi.get_stack()
is_prod = stack == "prod"

FUNCOES_DIR = "../aws-sam/functions"
FRONTEND_DIST = Path("../frontend/dist")
# Todas as rotas da API ficam sob /api; o resto do domínio é o frontend.
API_PREFIX = "/api"

# Nem todo sistema conhece esses tipos; sem eles a fonte iria para o S3 como
# application/octet-stream
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
RUNTIME = aws.lambda_.Runtime.PYTHON3D12

config = pulumi.Config()
aws_config = pulumi.Config("aws")
REGIAO = aws_config.require("region")

# --- Login com Google (Cognito) ---
# Só é ativado depois de configurar as credenciais do Google no stack:
#   pulumi config set googleClientId <id>
#   pulumi config set --secret googleClientSecret <secret>
# Sem elas, a API continua aceitando o header x-membro-id (modo de teste).
GOOGLE_CLIENT_ID = config.get("googleClientId")
usar_google = bool(GOOGLE_CLIENT_ID)

# O prefixo do domínio de login do Cognito precisa ser único na região; com o
# número da conta ele já é conhecido antes do deploy (o Google pede essa URL).
conta = aws.get_caller_identity().account_id
COGNITO_DOMINIO = f"quemfaz-{stack}-{conta}"
COGNITO_URL = f"https://{COGNITO_DOMINIO}.auth.{REGIAO}.amazoncognito.com"

if is_prod:
    DOMAIN = config.require("dominio")

    # O subdomínio tem a própria zona DNS, nesta conta. Para ela valer na
    # internet, o dono do domínio pai (o professor) cria um registro NS
    # apontando para os servidores de nome abaixo.
    # protect=True: o Pulumi recusa apagar ou recriar a zona (inclusive num
    # `pulumi destroy`). Uma zona nova teria outros NS e quebraria a delegação.
    zona = aws.route53.Zone(
        "quemfaz-zona",
        name=DOMAIN,
        opts=pulumi.ResourceOptions(protect=True),
    )
    zone_id = zona.zone_id

    # Mostra os NS assim que a zona existe: o primeiro deploy fica esperando
    # a validação do certificado, que só passa depois da delegação.
    zona.name_servers.apply(
        lambda ns: pulumi.log.info(
            f"Servidores de nome de {DOMAIN} (mande ao professor): " + ", ".join(ns)
        )
    )

# --- DynamoDB ---
membros = aws.dynamodb.Table(
    "membros",
    attributes=[
        aws.dynamodb.TableAttributeArgs(name="membroId", type="S"),
        aws.dynamodb.TableAttributeArgs(name="nucleoId", type="S"),
    ],
    hash_key="membroId",
    billing_mode="PAY_PER_REQUEST",
    global_secondary_indexes=[
        aws.dynamodb.TableGlobalSecondaryIndexArgs(
            name="nucleoId-index",
            hash_key="nucleoId",
            projection_type="ALL",
        )
    ],
)

nucleos = aws.dynamodb.Table(
    "nucleos",
    attributes=[aws.dynamodb.TableAttributeArgs(name="nucleoId", type="S")],
    hash_key="nucleoId",
    billing_mode="PAY_PER_REQUEST",
)

tarefas = aws.dynamodb.Table(
    "tarefas",
    attributes=[
        aws.dynamodb.TableAttributeArgs(name="nucleoId", type="S"),
        aws.dynamodb.TableAttributeArgs(name="tarefaId", type="S"),
    ],
    hash_key="nucleoId",
    range_key="tarefaId",
    billing_mode="PAY_PER_REQUEST",
)

# --- IAM ---
LEITURA = [
    "dynamodb:GetItem",
    "dynamodb:BatchGetItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:DescribeTable",
]
CRUD = LEITURA + [
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:DeleteItem",
    "dynamodb:BatchWriteItem",
]


def criar_role(name, acessos):
    """Cria a role de uma Lambda com acesso só às tabelas que ela usa."""
    role = aws.iam.Role(
        f"{name}-role",
        assume_role_policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        ),
    )

    aws.iam.RolePolicyAttachment(
        f"{name}-logs",
        role=role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )

    aws.iam.RolePolicy(
        f"{name}-dynamodb",
        role=role.id,
        policy=pulumi.Output.all(*[tabela.arn for tabela, _ in acessos]).apply(
            lambda arns: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": acoes,
                            "Resource": [arn, f"{arn}/index/*"],
                        }
                        for arn, (_, acoes) in zip(arns, acessos)
                    ],
                }
            )
        ),
    )
    return role


# --- API Gateway (HTTP API) ---
api = aws.apigatewayv2.Api("quemfaz-api", protocol_type="HTTP")

aws.apigatewayv2.Stage(
    "quemfaz-stage", api_id=api.id, name="$default", auto_deploy=True
)

# --- Lambdas ---
# O SAM empacota o layer em python/; aqui a estrutura é montada na mão.
comum_layer = aws.lambda_.LayerVersion(
    "quemfaz-comum",
    layer_name=f"quemfaz-comum-{stack}",
    compatible_runtimes=[RUNTIME],
    code=pulumi.AssetArchive(
        {"python/comum.py": pulumi.FileAsset(f"{FUNCOES_DIR}/comum/comum.py")}
    ),
)

lambda_env = aws.lambda_.FunctionEnvironmentArgs(
    variables={
        "MEMBROS_TABLE": membros.name,
        "NUCLEOS_TABLE": nucleos.name,
        "TAREFAS_TABLE": tarefas.name,
        # Com o Cognito ativo, as Lambdas ignoram o header x-membro-id
        **({"EXIGIR_TOKEN": "1"} if usar_google else {}),
    }
)


def public_function(pasta, rotas, acessos):
    """Cria uma Lambda de aws-sam/functions/<pasta> e publica suas rotas na API."""
    name = f"quemfaz-{pasta}"
    fn = aws.lambda_.Function(
        name,
        role=criar_role(name, acessos).arn,
        runtime=RUNTIME,
        handler="handler.handler",
        timeout=10,
        code=pulumi.FileArchive(f"{FUNCOES_DIR}/{pasta}"),
        layers=[comum_layer.arn],
        environment=lambda_env,
    )
    integration = aws.apigatewayv2.Integration(
        f"{name}-integration",
        api_id=api.id,
        integration_type="AWS_PROXY",
        integration_method="POST",
        integration_uri=fn.invoke_arn,
        # Os handlers leem event["resource"] e event["httpMethod"], que só
        # existem no formato 1.0 (o mesmo do SAM com evento do tipo Api).
        payload_format_version="1.0",
    )
    for evento, route_key in rotas.items():
        metodo, caminho = route_key.split(" ", 1)
        aws.apigatewayv2.Route(
            f"{name}-{evento}-route",
            api_id=api.id,
            # Os handlers usam endswith() e pathParameters, então o prefixo
            # não muda nada no código das Lambdas.
            route_key=f"{metodo} {API_PREFIX}{caminho}",
            target=integration.id.apply(lambda i: f"integrations/{i}"),
            # Com o Cognito ativo, o API Gateway recusa (401) quem não manda
            # um token válido, antes mesmo de chamar a Lambda.
            authorization_type="JWT" if authorizer else "NONE",
            authorizer_id=authorizer.id if authorizer else None,
        )
    aws.lambda_.Permission(
        f"{name}-apigw-permission",
        function=fn.name,
        action="lambda:InvokeFunction",
        principal="apigateway.amazonaws.com",
        source_arn=api.execution_arn.apply(lambda a: f"{a}/*/*"),
    )
    return fn


# --- Frontend (S3 privado, lido só pelo CloudFront) ---
# O build roda aqui mesmo, então `pulumi up` sozinho já publica o front atual.
# (npm install em vez de npm ci: não apaga o node_modules de um `npm run dev`
# que esteja rodando, e continua respeitando o package-lock.json)
for comando in (["npm", "install", "--no-audit", "--no-fund"], ["npm", "run", "build"]):
    r = subprocess.run(comando, cwd=FRONTEND_DIST.parent, capture_output=True, text=True)
    if r.returncode != 0:
        raise Exception(f"Falhou: {' '.join(comando)} em frontend/\n{r.stdout}\n{r.stderr}")

site = aws.s3.Bucket("quemfaz-frontend", force_destroy=True)

aws.s3.BucketPublicAccessBlock(
    "quemfaz-frontend-block",
    bucket=site.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

for arquivo in sorted(p for p in FRONTEND_DIST.rglob("*") if p.is_file()):
    chave = arquivo.relative_to(FRONTEND_DIST).as_posix()
    aws.s3.BucketObjectv2(
        f"site/{chave}",
        bucket=site.id,
        key=chave,
        source=pulumi.FileAsset(str(arquivo)),
        content_type=mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream",
        # Os arquivos em assets/ têm hash no nome (gerado pelo Vite), então
        # podem ficar em cache para sempre. O index.html aponta para eles e
        # precisa ser revalidado a cada acesso para o deploy novo aparecer
        # sem invalidar o cache do CloudFront.
        cache_control=(
            "public, max-age=31536000, immutable"
            if chave.startswith("assets/")
            else "no-cache"
        ),
    )

site_oac = aws.cloudfront.OriginAccessControl(
    "quemfaz-frontend-oac",
    origin_access_control_origin_type="s3",
    signing_behavior="always",
    signing_protocol="sigv4",
)

# --- CloudFront (+ ACM e Route53 em prod) ---
aliases = []
viewer_cert = aws.cloudfront.DistributionViewerCertificateArgs(
    cloudfront_default_certificate=True
)

if is_prod:
    # Certificados usados pelo CloudFront precisam estar em us-east-1
    us_east_1 = aws.Provider("us-east-1", region="us-east-1")

    cert = aws.acm.Certificate(
        "cert",
        domain_name=DOMAIN,
        validation_method="DNS",
        opts=pulumi.ResourceOptions(provider=us_east_1),
    )

    validation_record = aws.route53.Record(
        "cert-validation",
        name=cert.domain_validation_options[0].resource_record_name,
        zone_id=zone_id,
        type=cert.domain_validation_options[0].resource_record_type,
        records=[cert.domain_validation_options[0].resource_record_value],
        ttl=60,
    )

    cert_validation = aws.acm.CertificateValidation(
        "cert-val",
        certificate_arn=cert.arn,
        validation_record_fqdns=[validation_record.fqdn],
        opts=pulumi.ResourceOptions(provider=us_east_1),
    )

    aliases = [DOMAIN]
    viewer_cert = aws.cloudfront.DistributionViewerCertificateArgs(
        acm_certificate_arn=cert_validation.certificate_arn,
        ssl_support_method="sni-only",
        minimum_protocol_version="TLSv1.2_2021",
    )

caching_optimized = aws.cloudfront.get_cache_policy(name="Managed-CachingOptimized")
all_viewer_except_host = aws.cloudfront.get_origin_request_policy(
    name="Managed-AllViewerExceptHostHeader"
)

# O CloudFront só repassa o header Authorization (o token do login) quando ele
# faz parte da chave de cache. Com TTL padrão 0, nada é guardado em cache de
# fato: as respostas das Lambdas não mandam Cache-Control.
api_cache = aws.cloudfront.CachePolicy(
    "quemfaz-api-cache",
    min_ttl=0,
    default_ttl=0,
    max_ttl=1,
    parameters_in_cache_key_and_forwarded_to_origin=aws.cloudfront.CachePolicyParametersInCacheKeyAndForwardedToOriginArgs(
        headers_config=aws.cloudfront.CachePolicyParametersInCacheKeyAndForwardedToOriginHeadersConfigArgs(
            header_behavior="whitelist",
            headers=aws.cloudfront.CachePolicyParametersInCacheKeyAndForwardedToOriginHeadersConfigHeadersArgs(
                items=["Authorization"]
            ),
        ),
        cookies_config=aws.cloudfront.CachePolicyParametersInCacheKeyAndForwardedToOriginCookiesConfigArgs(
            cookie_behavior="none"
        ),
        query_strings_config=aws.cloudfront.CachePolicyParametersInCacheKeyAndForwardedToOriginQueryStringsConfigArgs(
            query_string_behavior="all"
        ),
    ),
)

api_hostname = api.api_endpoint.apply(lambda e: e.replace("https://", "").split("/")[0])

distribution = aws.cloudfront.Distribution(
    "quemfaz-cdn",
    enabled=True,
    is_ipv6_enabled=True,
    http_version="http2and3",
    aliases=aliases,
    default_root_object="index.html",
    origins=[
        aws.cloudfront.DistributionOriginArgs(
            domain_name=api_hostname,
            origin_id="api",
            custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
                http_port=80,
                https_port=443,
                origin_protocol_policy="https-only",
                origin_ssl_protocols=["TLSv1.2"],
            ),
        ),
        aws.cloudfront.DistributionOriginArgs(
            domain_name=site.bucket_regional_domain_name,
            origin_id="site",
            origin_access_control_id=site_oac.id,
        ),
    ],
    # /api/* → API Gateway, sem cache (respostas dependem do usuário)
    ordered_cache_behaviors=[
        aws.cloudfront.DistributionOrderedCacheBehaviorArgs(
            path_pattern=f"{API_PREFIX}/*",
            target_origin_id="api",
            viewer_protocol_policy="redirect-to-https",
            allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
            cached_methods=["GET", "HEAD"],
            cache_policy_id=api_cache.id,
            origin_request_policy_id=all_viewer_except_host.id,
        )
    ],
    # Todo o resto → frontend no S3, com cache
    default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
        target_origin_id="site",
        viewer_protocol_policy="redirect-to-https",
        allowed_methods=["GET", "HEAD"],
        cached_methods=["GET", "HEAD"],
        cache_policy_id=caching_optimized.id,
        compress=True,
    ),
    viewer_certificate=viewer_cert,
    restrictions=aws.cloudfront.DistributionRestrictionsArgs(
        geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
            restriction_type="none"
        )
    ),
)

# Só esta distribuição do CloudFront pode ler o bucket
aws.s3.BucketPolicy(
    "quemfaz-frontend-policy",
    bucket=site.id,
    policy=pulumi.Output.all(site.arn, distribution.arn).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "cloudfront.amazonaws.com"},
                        "Action": "s3:GetObject",
                        "Resource": f"{args[0]}/*",
                        "Condition": {"StringEquals": {"AWS:SourceArn": args[1]}},
                    }
                ],
            }
        )
    ),
)

if is_prod:
    for rtype in ["A", "AAAA"]:
        aws.route53.Record(
            f"alias-{rtype}",
            zone_id=zone_id,
            name=DOMAIN,
            type=rtype,
            aliases=[
                aws.route53.RecordAliasArgs(
                    name=distribution.domain_name,
                    zone_id=distribution.hosted_zone_id,
                    evaluate_target_health=False,
                )
            ],
        )

# Output nos dois casos (em prod o endereço é fixo, mas o resto do código
# usa .apply nele)
site_url = (
    pulumi.Output.from_input(f"https://{DOMAIN}")
    if is_prod
    else distribution.domain_name.apply(lambda d: f"https://{d}")
)

# --- Cognito: login com Google (UC01) ---
authorizer = None
config_frontend = {}

if usar_google:
    usuarios = aws.cognito.UserPool(
        "quemfaz-usuarios",
        name=f"quemfaz-{stack}",
        # Ninguém cria conta com senha: só entra quem vem pelo Google
        admin_create_user_config=aws.cognito.UserPoolAdminCreateUserConfigArgs(
            allow_admin_create_user_only=True
        ),
    )

    aws.cognito.UserPoolDomain(
        "quemfaz-login",
        domain=COGNITO_DOMINIO,
        user_pool_id=usuarios.id,
    )

    google = aws.cognito.IdentityProvider(
        "google",
        user_pool_id=usuarios.id,
        provider_name="Google",
        provider_type="Google",
        provider_details={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": config.require_secret("googleClientSecret"),
            "authorize_scopes": "openid email profile",
            # O Cognito preenche estes campos sozinho; declarados aqui, o
            # Pulumi não acusa diferença a cada deploy.
            "attributes_url": "https://people.googleapis.com/v1/people/me?personFields=",
            "attributes_url_add_attributes": "true",
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "oidc_issuer": "https://accounts.google.com",
            "token_request_method": "POST",
            "token_url": "https://www.googleapis.com/oauth2/v4/token",
        },
        attribute_mapping={
            "email": "email",
            "name": "name",
            "given_name": "given_name",
            "username": "sub",
        },
    )

    # O Google devolve a pessoa para a raiz do site, que termina o login
    voltar_para = site_url.apply(lambda u: [f"{u}/"])
    cliente_web = aws.cognito.UserPoolClient(
        "quemfaz-web",
        name=f"quemfaz-web-{stack}",
        user_pool_id=usuarios.id,
        # App no navegador: sem segredo, com PKCE
        generate_secret=False,
        allowed_oauth_flows_user_pool_client=True,
        allowed_oauth_flows=["code"],
        allowed_oauth_scopes=["openid", "email", "profile"],
        supported_identity_providers=["Google"],
        callback_urls=voltar_para,
        logout_urls=voltar_para,
        opts=pulumi.ResourceOptions(depends_on=[google]),
    )

    authorizer = aws.apigatewayv2.Authorizer(
        "quemfaz-cognito",
        api_id=api.id,
        authorizer_type="JWT",
        identity_sources=["$request.header.Authorization"],
        jwt_configuration=aws.apigatewayv2.AuthorizerJwtConfigurationArgs(
            # O frontend manda o id_token, cujo "aud" é o id do cliente
            audiences=[cliente_web.id],
            issuer=usuarios.endpoint.apply(lambda e: f"https://{e}"),
        ),
    )

    config_frontend = {"cognito": {"url": COGNITO_URL, "clientId": cliente_web.id}}

# --- Rotas da API (depois do Cognito, que protege todas elas) ---
public_function(
    "login",
    {"login": "POST /login"},
    [(membros, CRUD)],
)

public_function(
    "nucleos",
    {
        "criar": "POST /nucleos",
        "entrar": "POST /nucleos/{nucleoId}/membros",
        "consultar": "GET /nucleos/{nucleoId}",
    },
    [(membros, CRUD), (nucleos, CRUD)],
)

public_function(
    "tarefas",
    {
        "listar": "GET /tarefas",
        "criar": "POST /tarefas",
        "escolher": "POST /tarefas/{tarefaId}/escolher",
        "concluir": "POST /tarefas/{tarefaId}/concluir",
    },
    [(membros, LEITURA), (tarefas, CRUD)],
)

public_function(
    "aprovar",
    {"aprovar": "POST /aprovar"},
    [(membros, CRUD), (tarefas, CRUD)],
)

public_function(
    "placar",
    {"placar": "GET /placar"},
    [(membros, LEITURA)],
)

# Configuração lida pelo frontend ao abrir (sem Cognito: {} = modo de teste)
aws.s3.BucketObjectv2(
    "site/config.json",
    bucket=site.id,
    key="config.json",
    content=pulumi.Output.from_input(config_frontend).apply(json.dumps),
    content_type="application/json",
    cache_control="no-cache",
)

pulumi.export("membros_table", membros.name)
pulumi.export("nucleos_table", nucleos.name)
pulumi.export("tarefas_table", tarefas.name)
pulumi.export("api_url", api.api_endpoint)
pulumi.export("frontend_bucket", site.bucket)
# URL a cadastrar no Google Cloud ("URIs de redirecionamento autorizados")
pulumi.export("google_redirect_uri", f"{COGNITO_URL}/oauth2/idpresponse")
pulumi.export("login_google", "ativo" if usar_google else "desativado")
if is_prod:
    pulumi.export("name_servers", zona.name_servers)
pulumi.export("url", site_url)
