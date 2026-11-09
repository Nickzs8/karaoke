/**
 * Player de Áudio e Sincronizador de Letras
 */

export class AudioPlayer {
  constructor() {
    this.audio = new Audio();
    this.audio.preload = "auto";
    this.lyricsLines = [];
    this.currentLineIndex = -1;
    this.lyricsOffset = 0.0;

    // Callbacks de eventos
    this.onTimeUpdate = null;
    this.onLineChange = null;
    this.onPlay = null;
    this.onPause = null;
    this.onEnded = null;

    this._bindEvents();
  }

  _bindEvents() {
    this.audio.addEventListener("timeupdate", () => {
      const currentTime = this.audio.currentTime || 0;
      const duration = this.audio.duration || 0;
      const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

      if (this.onTimeUpdate) {
        this.onTimeUpdate(currentTime, duration, progressPercent);
      }

      this._syncLyrics(currentTime);
    });

    this.audio.addEventListener("play", () => {
      if (this.onPlay) this.onPlay();
    });

    this.audio.addEventListener("pause", () => {
      if (this.onPause) this.onPause();
    });

    this.audio.addEventListener("ended", () => {
      if (this.onEnded) this.onEnded();
    });
  }

  /**
   * Carrega a faixa de áudio e as letras sincronizadas.
   * @param {string} audioUrl
   * @param {Array} lyricsLines
   * @param {number} offset
   */
  load(audioUrl, lyricsLines = [], offset = 0.0) {
    this.lyricsLines = lyricsLines;
    this.lyricsOffset = Number(offset) || 0.0;
    this.currentLineIndex = -1;
    this.audio.src = audioUrl;
    this.audio.load();
  }

  /**
   * Define o offset de sincronia das letras em segundos.
   * Valores positivos atrasam a letra (para músicas com intro/silêncio).
   * Valores negativos adiantam a letra.
   * @param {number} offsetSeconds
   */
  setLyricsOffset(offsetSeconds) {
    this.lyricsOffset = Number(offsetSeconds) || 0.0;
    this._syncLyrics(this.getCurrentTime());
  }

  getLyricsOffset() {
    return this.lyricsOffset;
  }

  async play() {
    return this.audio.play();
  }

  pause() {
    this.audio.pause();
  }

  seek(seconds) {
    if (this.audio.duration) {
      this.audio.currentTime = Math.max(0, Math.min(seconds, this.audio.duration));
    }
  }

  seekPercent(percent) {
    if (this.audio.duration) {
      const targetTime = (percent / 100) * this.audio.duration;
      this.seek(targetTime);
    }
  }

  setVolume(volume) {
    this.audio.volume = Math.max(0, Math.min(1, volume));
  }

  isPlaying() {
    return !this.audio.paused && !this.audio.ended;
  }

  getCurrentTime() {
    return this.audio.currentTime || 0;
  }

  getDuration() {
    return this.audio.duration || 0;
  }

  _syncLyrics(currentTime) {
    if (!this.lyricsLines || this.lyricsLines.length === 0) return;

    // Tempo efetivo ajustado pelo offset temporal de sincronia
    const effectiveTime = currentTime - this.lyricsOffset;

    // Encontra o verso correspondente ao tempo atual
    let activeIndex = -1;
    for (let i = 0; i < this.lyricsLines.length; i++) {
      const line = this.lyricsLines[i];
      if (effectiveTime >= line.start_time && effectiveTime <= line.end_time) {
        activeIndex = i;
        break;
      }
    }

    // Se o verso mudou, notifica o listener
    if (activeIndex !== this.currentLineIndex) {
      this.currentLineIndex = activeIndex;
      if (this.onLineChange) {
        const activeLine = activeIndex >= 0 ? this.lyricsLines[activeIndex] : null;
        this.onLineChange(activeLine, activeIndex);
      }
    }
  }
}
