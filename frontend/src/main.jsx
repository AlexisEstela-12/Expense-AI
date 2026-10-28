import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./style.css";
import "./styles/components.css";
import "./styles/responsive.css";
import "./styles/pages.css";
import "./styles/chat.css";
import "./styles/auth.css";

createRoot(document.getElementById("root")).render(<App />);
