const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'
).replace(/\/+$/, '');

export async function fetchAPI(endpoint: string) {
  try {
    const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const response = await fetch(`${API_BASE_URL}${path}`);

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const dados = await response.json();
    if (!Array.isArray(dados)) throw new Error('A API não retornou uma lista.');

    return dados;
  } catch (error) {
    console.error(`Erro ao carregar ${endpoint}:`, error);
    return null;
  }
}
