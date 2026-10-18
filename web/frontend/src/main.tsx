import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import "./studio-theme.css";

const preloadedStylesheet = document.querySelector<HTMLLinkElement>("link[data-creatoros-style-preload]");
if (preloadedStylesheet) preloadedStylesheet.rel = "stylesheet";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
