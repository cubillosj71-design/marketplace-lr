import axios from "axios";

// URL base de la API REST (/api/v1). En Render llega por la variable VITE_API_URL.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1",
});
