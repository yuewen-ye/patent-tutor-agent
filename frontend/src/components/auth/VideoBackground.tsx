import { cn } from "@/lib/utils";
import { DeskScene } from "./DeskScene";

type VideoBackgroundProps = {
  /** Public URL of the background video, e.g. /auth-bg.mp4 */
  src: string;
  /** Optional poster image shown while the video loads. */
  poster?: string;
  className?: string;
};

export function VideoBackground({
  src,
  poster,
  className,
}: VideoBackgroundProps) {
  return (
    <div
      className={cn(
        "absolute inset-0 overflow-hidden bg-[#FFF7ED]",
        className
      )}
    >
      {/* Static SVG scene serves as the loading / fallback surface. */}
      <DeskScene className="h-full w-full" />

      {/* Video layer plays above the SVG when the file is present. */}
      <video
        autoPlay
        muted
        loop
        playsInline
        poster={poster}
        className="absolute inset-0 h-full w-full object-cover object-center"
      >
        <source src={src} type="video/mp4" />
      </video>

      {/* Left-to-right readability veil that mirrors the warm wall tone.
          Lighter on the right so the original video colors remain vivid. */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-[#FFF7ED]/90 via-[#FFF7ED]/45 to-transparent" />
    </div>
  );
}
