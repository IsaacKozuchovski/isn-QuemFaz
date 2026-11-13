import json
import mimetypes
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

if is_prod:
    config = pulumi.Config()
    aws_config = pulumi.Config("aws")

    DOMAIN = config.require("dominio")
    zone_id = aws_config.require("zoneId")

    # A hosted zone já existe e fica em outra conta: os registros DNS são
    # criados assumindo a role que dá acesso a ela.
    route53 = aws.Provider(
        "route53",
        region=aws_config.require("region"),
        assume_roles=[
            aws.ProviderAssumeRoleArgs(
                role_arn=aws_config.require("roleArn"),
                external_id=aws_config.require("externalId"),
            )
        ],
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
        )
    aws.lambda_.Permission(
        f"{name}-apigw-permission",
        function=fn.name,
        action="lambda:InvokeFunction",
        principal="apigateway.amazonaws.com",
        source_arn=api.execution_arn.apply(lambda a: f"{a}/*/*"),
    )
    return fn


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

# --- Frontend (S3 privado, lido só pelo CloudFront) ---
if not (FRONTEND_DIST / "index.html").exists():
    raise Exception(
        "frontend/dist não encontrado: rode `npm ci && npm run build` em frontend/ antes"
    )

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
        opts=pulumi.ResourceOptions(provider=route53),
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

caching_disabled = aws.cloudfront.get_cache_policy(name="Managed-CachingDisabled")
caching_optimized = aws.cloudfront.get_cache_policy(name="Managed-CachingOptimized")
all_viewer_except_host = aws.cloudfront.get_origin_request_policy(
    name="Managed-AllViewerExceptHostHeader"
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
            cache_policy_id=caching_disabled.id,
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
            opts=pulumi.ResourceOptions(provider=route53),
        )

pulumi.export("membros_table", membros.name)
pulumi.export("nucleos_table", nucleos.name)
pulumi.export("tarefas_table", tarefas.name)
pulumi.export("api_url", api.api_endpoint)
pulumi.export("frontend_bucket", site.bucket)
pulumi.export(
    "url",
    (
        f"https://{DOMAIN}"
        if is_prod
        else distribution.domain_name.apply(lambda d: f"https://{d}")
    ),
)
