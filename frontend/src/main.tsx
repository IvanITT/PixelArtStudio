import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { useStudio } from "./store/studio";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

void useStudio.getState().bootstrap();
