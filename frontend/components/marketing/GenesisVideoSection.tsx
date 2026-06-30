"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const SCROLL_KEYS = new Set(["ArrowDown", "ArrowUp", "PageDown", "PageUp", " ", "End", "Home"]);

export function GenesisVideoSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const unlockRef = useRef<(() => void) | null>(null);
  const hasEndedRef = useRef(false);
  const hasScrolledAwayRef = useRef(false);
  const [showScrollHint, setShowScrollHint] = useState(false);
  const [isStaticMode, setIsStaticMode] = useState(true); // SSR-safe default

  useEffect(() => {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isMobile = window.innerWidth < 1024;
    const staticMode = prefersReduced || isMobile;
    setIsStaticMode(staticMode);
    // In static mode there's no video, so show the hint immediately.
    // Do NOT set this via hintVisible = showScrollHint || isStaticMode because
    // isStaticMode starts as true (SSR default) and would flash the hint before
    // the video even starts playing on desktop.
    if (staticMode) setShowScrollHint(true);
  }, []);

  const lockScroll = useCallback((): (() => void) => {
    const onWheel = (e: WheelEvent) => e.preventDefault();
    const onTouch = (e: TouchEvent) => e.preventDefault();
    const onKey = (e: KeyboardEvent) => {
      if (SCROLL_KEYS.has(e.key)) e.preventDefault();
    };
    // Hide only vertical scroll during video; horizontal stays hidden via html rule.
    document.body.style.overflowY = "hidden";
    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("touchmove", onTouch, { passive: false });
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflowY = "";
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("touchmove", onTouch);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  const unlock = useCallback(() => {
    unlockRef.current?.();
    unlockRef.current = null;
  }, []);

  const playVideo = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = 0;
    setShowScrollHint(false);
    unlockRef.current = lockScroll();
    video.play().catch(() => {
      // Autoplay blocked — restore hasEnded so scroll-back-to-top can retry.
      hasEndedRef.current = true;
      unlock();
      setShowScrollHint(true);
    });
  }, [lockScroll, unlock]);

  // autoPlay on a dynamically-inserted <video> is unreliable in Chrome —
  // the attribute is only honored on initial parse. Imperative play() is the fix.
  useEffect(() => {
    if (isStaticMode) return;
    playVideo();
    return unlock;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStaticMode]);

  // Restart when user scrolls all the way back to the top.
  // IntersectionObserver was unreliable for this: at threshold:0.1 it fires when
  // the bottom 10% of genesis enters the viewport (scrolling up), at which point
  // boundingClientRect.top ≈ -810px — the "at top" guard never passed.
  // Genesis is the first section, so scrollY < 50 reliably means "at the top".
  useEffect(() => {
    if (isStaticMode) return;

    const handleScroll = () => {
      const y = window.scrollY;
      if (hasEndedRef.current) {
        // Track that the user scrolled away from genesis before allowing replay.
        // Without this guard, the first scroll event after video ends fires at
        // scrollY ≈ 0–50, immediately re-triggering playVideo and re-locking scroll.
        if (y > 300) hasScrolledAwayRef.current = true;
        if (y < 100 && hasScrolledAwayRef.current) {
          hasEndedRef.current = false;
          hasScrolledAwayRef.current = false;
          playVideo();
        }
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [isStaticMode, playVideo]);

  const handleVideoEnded = useCallback(() => {
    hasEndedRef.current = true;
    hasScrolledAwayRef.current = false;
    unlock();
    setShowScrollHint(true);
  }, [unlock]);

  const hintVisible = showScrollHint;

  return (
    <section
      ref={sectionRef}
      id="genesis"
      className="relative w-full h-screen overflow-hidden bg-black"
      aria-label="BioShield — génesis biológico"
    >
      {!isStaticMode && (
        <video
          ref={videoRef}
          muted
          playsInline
          src="/videos/bioshield-genesis.mp4"
          onEnded={handleVideoEnded}
          className="absolute inset-0 w-full h-full object-cover"
        />
      )}

      {/* Subtle bottom gradient → softens the cut to the next section */}
      <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-black/60 to-transparent pointer-events-none" />

      {/* top-20 = 80px — clears the fixed navbar (64px) with a bit of breathing room */}
      <div
        className={`absolute top-20 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 transition-opacity duration-700 ${
          hintVisible ? "opacity-100" : "opacity-0"
        }`}
        aria-hidden="true"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-white/60 animate-bounce"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-white/60">
          scroll
        </span>
      </div>
    </section>
  );
}
