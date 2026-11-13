import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
// Fonte do logo, embutida no build (só o peso 700 e só caracteres latinos)
import "@fontsource/fredoka/latin-700.css";
import "./style.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
