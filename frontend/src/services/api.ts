import axios from "axios";
export const api = axios.create({ baseURL: "/api", timeout: 180000 });
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401) {
      sessionStorage.removeItem("token");
      window.dispatchEvent(new Event("session-expired"));
    }
    return Promise.reject(e);
  },
);
export const get = async (path: string) => (await api.get(path)).data;
export const post = async (path: string, body: unknown = {}) =>
  (await api.post(path, body)).data;
export const errorText = (e: unknown) =>
  axios.isAxiosError(e)
    ? typeof e.response?.data?.detail === "string"
      ? e.response.data.detail
      : e.message
    : String(e);
