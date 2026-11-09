/**
 * Módulo de Integração com a API RESTful do Karaokê AI
 */

const API_BASE = "/api";

export const api = {
  /**
   * Recupera a lista de músicas prontas para cantar.
   * @param {boolean} onlyReady
   * @returns {Promise<Array>}
   */
  async getSongs(onlyReady = true) {
    const response = await fetch(`${API_BASE}/songs?only_ready=${onlyReady}`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Falha ao carregar catálogo de músicas.");
    }
    return response.json();
  },

  /**
   * Recupera os dados de uma música específica pelo ID.
   * @param {string} songId
   * @returns {Promise<Object>}
   */
  async getSong(songId) {
    try {
      const response = await fetch(`${API_BASE}/songs/${encodeURIComponent(songId)}`);
      if (response.ok) {
        return await response.json();
      }
    } catch {
      // Fallback para getSongs caso a rota direta falhe
    }

    const songs = await this.getSongs(false);
    const found = songs.find((s) => s.id === songId);
    if (!found) {
      throw new Error("Música não encontrada no catálogo.");
    }
    return found;
  },

  /**
   * Dispara o preparo de música a partir de URL do YouTube ou termo de busca.
   * @param {string} queryOrUrl
   * @param {string|null} title
   * @param {string|null} artist
   * @returns {Promise<Object>}
   */
  async prepareSongByUrl(queryOrUrl, title = null, artist = null) {
    const payload = {
      query_or_url: queryOrUrl.trim(),
      title: title?.trim() || null,
      artist: artist?.trim() || null,
    };

    const response = await fetch(`${API_BASE}/songs/prepare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Erro ao preparar música a partir do YouTube.");
    }
    return response.json();
  },

  /**
   * Dispara o preparo enviando um arquivo local de áudio (.mp3, .wav).
   * @param {File} file
   * @param {string|null} title
   * @param {string|null} artist
   * @returns {Promise<Object>}
   */
  async prepareSongByFile(file, title = null, artist = null) {
    const formData = new FormData();
    formData.append("file", file);
    if (title?.trim()) formData.append("title", title.trim());
    if (artist?.trim()) formData.append("artist", artist.trim());

    const response = await fetch(`${API_BASE}/songs/prepare`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Erro ao processar arquivo de áudio enviado.");
    }
    return response.json();
  },

  /**
   * Busca a letra sincronizada estruturada em JSON para uma música.
   * @param {string} songId
   * @returns {Promise<Object>}
   */
  async getLyrics(songId) {
    const response = await fetch(`${API_BASE}/songs/${songId}/lyrics`);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Letra sincronizada não encontrada.");
    }
    return response.json();
  },

  /**
   * Envia o áudio gravado do microfone para avaliação e geração da nota.
   * @param {string} songId
   * @param {Blob} audioBlob
   * @returns {Promise<Object>}
   */
  async evaluatePerformance(songId, audioBlob) {
    const formData = new FormData();
    formData.append("song_id", songId);

    const mime = (audioBlob && audioBlob.type) ? audioBlob.type.toLowerCase() : "";
    const ext = mime.includes("webm")
      ? "webm"
      : mime.includes("ogg")
      ? "ogg"
      : mime.includes("mp4") || mime.includes("m4a")
      ? "m4a"
      : "wav";

    formData.append("audio_file", audioBlob, `recording_${Date.now()}.${ext}`);

    const response = await fetch(`${API_BASE}/performances/evaluate`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Falha ao avaliar a performance vocal.");
    }
    return response.json();
  },
};
