import React from "react";
import { createRoot } from "react-dom/client";
import ProductApp from "./product/App.jsx";
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ProductApp />
  </React.StrictMode>,
);
