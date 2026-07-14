"use client";

import { useState } from "react";

interface FormatOption {
  format_id: string;
  ext: string;
  resolution: string;
  height: number | null;
  fps: number | null;
  vcodec: string;
  acodec: string;
  filesize: number | null;
  filesize_approx: number | null;
  filesize_human: string;
  is_video: boolean;
  is_audio: boolean;
  label: string;
}

interface VideoInfo {
  id: string;
  title: string;
  duration: number | null;
  duration_human: string;
  thumbnail: string | null;
  uploader: string | null;
  view_count: number | null;
}

interface AnalyzeResult {
  video: VideoInfo;
  video_options: FormatOption[];
  audio_options: FormatOption[];
  advanced_formats: FormatOption[];
}

interface DownloadResult {
  job_id: string;
  state: string;
  download_url: string | null;
  filename: string | null;
  expires_at: string | null;
  message: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

export default function HomePage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [videoOptions, setVideoOptions] = useState<FormatOption[]>([]);
  const [audioOptions, setAudioOptions] = useState<FormatOption[]>([]);
  const [selectedQuality, setSelectedQuality] = useState("");
  const [selectedFormatId, setSelectedFormatId] = useState("");
  const [mediaType, setMediaType] = useState<"video" | "audio">("video");
  const [audioFormat, setAudioFormat] = useState<"mp3" | "m4a" | "opus">("mp3");
  const [deliveryMode, setDeliveryMode] = useState<"direct" | "link">("link");
  const [downloadResult, setDownloadResult] = useState<DownloadResult | null>(null);
  const [progress, setProgress] = useState("");

  async function handleAnalyze() {
    if (!url.trim()) {
      setError("Please enter a YouTube URL.");
      return;
    }

    setLoading(true);
    setError("");
    setVideoInfo(null);
    setVideoOptions([]);
    setAudioOptions([]);
    setSelectedQuality("");
    setSelectedFormatId("");
    setDownloadResult(null);
    setProgress("Analyzing…");

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (API_KEY) headers["X-API-Key"] = API_KEY;

      const res = await fetch(`${API_BASE}/api/v1/analyze`, {
        method: "POST",
        headers,
        body: JSON.stringify({ url: url.trim() }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || data.error || "Analysis failed.");
      }

      const result: AnalyzeResult = data;
      setVideoInfo(result.video);
      setVideoOptions(result.video_options);
      setAudioOptions(result.audio_options);

      if (result.video_options.length > 0) {
        setSelectedFormatId(result.video_options[0].format_id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred.");
    } finally {
      setLoading(false);
      setProgress("");
    }
  }

  async function handleDownload() {
    setLoading(true);
    setError("");
    setDownloadResult(null);
    setProgress("Downloading…");

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (API_KEY) headers["X-API-Key"] = API_KEY;

      const body: Record<string, unknown> = {
        url: url.trim(),
        quality: selectedQuality || undefined,
        format_id: selectedFormatId || undefined,
        type: mediaType,
        delivery: deliveryMode,
        audio_format: mediaType === "audio" ? audioFormat : undefined,
      };

      const res = await fetch(`${API_BASE}/api/v1/download`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });

      if (deliveryMode === "direct" && res.ok) {
        // File download
        const blob = await res.blob();
        const disposition = res.headers.get("content-disposition");
        const filename = disposition
          ? disposition.split("filename=")[1]?.replace(/"/g, "")
          : `download.${mediaType === "audio" ? audioFormat : "mp4"}`;

        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);

        setDownloadResult({
          job_id: "",
          state: "ready",
          download_url: null,
          filename,
          expires_at: null,
          message: "File downloaded successfully!",
        });
      } else {
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || data.error || "Download failed.");
        }
        setDownloadResult(data);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred.");
    } finally {
      setLoading(false);
      setProgress("");
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-sm">
        <div className="mx-auto max-w-4xl px-6 py-6">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🎬</span>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">YouTube Downloader</h1>
              <p className="text-sm text-slate-400">Analyze, select quality, and download</p>
            </div>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-8 space-y-8">
        {/* URL Input */}
        <section className="rounded-2xl bg-slate-800/60 p-6 border border-slate-700/50">
          <label className="block text-sm font-medium text-slate-300 mb-2">
            YouTube URL
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
              placeholder="https://www.youtube.com/watch?v=..."
              className="flex-1 rounded-lg bg-slate-900/60 border border-slate-600 px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-3 font-semibold transition-colors"
            >
              {loading && progress ? progress : "Analyze"}
            </button>
          </div>
        </section>

        {/* Error */}
        {error && (
          <div className="rounded-xl bg-red-900/30 border border-red-700/50 p-4 text-red-300">
            ❌ {error}
          </div>
        )}

        {/* Video Info */}
        {videoInfo && (
          <section className="rounded-2xl bg-slate-800/60 p-6 border border-slate-700/50">
            <div className="flex gap-6">
              {videoInfo.thumbnail && (
                <img
                  src={videoInfo.thumbnail}
                  alt={videoInfo.title}
                  className="w-48 h-28 object-cover rounded-lg flex-shrink-0"
                />
              )}
              <div className="min-w-0">
                <h2 className="text-lg font-semibold truncate">{videoInfo.title}</h2>
                <div className="mt-2 space-y-1 text-sm text-slate-400">
                  {videoInfo.uploader && <p>👤 {videoInfo.uploader}</p>}
                  <p>⏱️ {videoInfo.duration_human}</p>
                  {videoInfo.view_count && (
                    <p>👁️ {videoInfo.view_count.toLocaleString()} views</p>
                  )}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Quality Selection */}
        {videoInfo && (
          <section className="rounded-2xl bg-slate-800/60 p-6 border border-slate-700/50 space-y-6">
            {/* Media Type */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-3">
                Media Type
              </label>
              <div className="flex gap-3">
                <button
                  onClick={() => setMediaType("video")}
                  className={`rounded-lg px-5 py-2.5 font-medium transition-colors ${
                    mediaType === "video"
                      ? "bg-blue-600 text-white"
                      : "bg-slate-700/60 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  🎬 Video
                </button>
                <button
                  onClick={() => setMediaType("audio")}
                  className={`rounded-lg px-5 py-2.5 font-medium transition-colors ${
                    mediaType === "audio"
                      ? "bg-blue-600 text-white"
                      : "bg-slate-700/60 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  🎵 Audio Only
                </button>
              </div>
            </div>

            {/* Quality */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-3">
                {mediaType === "video" ? "Video Quality" : "Audio Quality"}
              </label>
              {mediaType === "video" ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {videoOptions.map((opt) => (
                    <button
                      key={opt.format_id}
                      onClick={() => {
                        setSelectedFormatId(opt.format_id);
                        setSelectedQuality("");
                      }}
                      className={`rounded-lg px-4 py-2.5 text-sm text-left transition-colors ${
                        selectedFormatId === opt.format_id
                          ? "bg-blue-600 text-white"
                          : "bg-slate-700/60 text-slate-300 hover:bg-slate-700"
                      }`}
                    >
                      <div className="font-medium">{opt.height ? `${opt.height}p` : opt.resolution}</div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        {opt.ext.toUpperCase()} {opt.filesize_human && `· ${opt.filesize_human}`}
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {audioOptions.map((opt) => (
                    <button
                      key={opt.format_id}
                      onClick={() => {
                        setSelectedFormatId(opt.format_id);
                        setSelectedQuality("");
                      }}
                      className={`rounded-lg px-4 py-2.5 text-sm text-left transition-colors ${
                        selectedFormatId === opt.format_id
                          ? "bg-blue-600 text-white"
                          : "bg-slate-700/60 text-slate-300 hover:bg-slate-700"
                      }`}
                    >
                      <div className="font-medium">{opt.acodec?.toUpperCase() || opt.ext.toUpperCase()}</div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        {opt.ext.toUpperCase()} {opt.filesize_human && `· ${opt.filesize_human}`}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Audio Format (when audio only) */}
            {mediaType === "audio" && (
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-3">
                  Audio Format
                </label>
                <div className="flex gap-2">
                  {(["mp3", "m4a", "opus"] as const).map((fmt) => (
                    <button
                      key={fmt}
                      onClick={() => setAudioFormat(fmt)}
                      className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                        audioFormat === fmt
                          ? "bg-blue-600 text-white"
                          : "bg-slate-700/60 text-slate-300 hover:bg-slate-700"
                      }`}
                    >
                      {fmt.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Delivery Mode */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-3">
                Delivery Mode
              </label>
              <div className="flex gap-3">
                <button
                  onClick={() => setDeliveryMode("direct")}
                  className={`rounded-lg px-5 py-2.5 font-medium transition-colors ${
                    deliveryMode === "direct"
                      ? "bg-blue-600 text-white"
                      : "bg-slate-700/60 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  📎 Direct Download
                </button>
                <button
                  onClick={() => setDeliveryMode("link")}
                  className={`rounded-lg px-5 py-2.5 font-medium transition-colors ${
                    deliveryMode === "link"
                      ? "bg-blue-600 text-white"
                      : "bg-slate-700/60 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  🔗 Download Link
                </button>
              </div>
            </div>

            {/* Download Button */}
            <button
              onClick={handleDownload}
              disabled={loading || !selectedFormatId}
              className="w-full rounded-lg bg-green-600 hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed py-4 text-lg font-bold transition-colors"
            >
              {loading ? (progress || "Processing…") : "⬇️ Download"}
            </button>
          </section>
        )}

        {/* Download Result */}
        {downloadResult && (
          <section className="rounded-2xl bg-green-900/20 border border-green-700/50 p-6">
            <div className="flex items-start gap-4">
              <span className="text-3xl">✅</span>
              <div>
                <h3 className="text-lg font-semibold text-green-300">Download Ready</h3>
                {downloadResult.filename && (
                  <p className="text-sm text-slate-400 mt-1">📄 {downloadResult.filename}</p>
                )}
                {downloadResult.download_url && (
                  <a
                    href={downloadResult.download_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 inline-block rounded-lg bg-blue-600 hover:bg-blue-500 px-5 py-2.5 font-medium transition-colors"
                  >
                    🔗 Open Download Link
                  </a>
                )}
                {downloadResult.expires_at && (
                  <p className="text-sm text-slate-400 mt-2">
                    ⏰ Expires: {new Date(downloadResult.expires_at).toLocaleString()}
                  </p>
                )}
                {downloadResult.message && !downloadResult.download_url && (
                  <p className="text-sm text-slate-400 mt-2">{downloadResult.message}</p>
                )}
              </div>
            </div>
          </section>
        )}

        {/* Footer */}
        <footer className="text-center text-sm text-slate-500 py-8 border-t border-slate-800">
          <p>
            ⚠️ For personal/archival use only. Respect copyright and YouTube Terms of Service.
          </p>
          <p className="mt-1">
            <a href="/docs/legal-disclaimer" className="underline hover:text-slate-400">
              Legal Disclaimer
            </a>
          </p>
        </footer>
      </div>
    </main>
  );
}
