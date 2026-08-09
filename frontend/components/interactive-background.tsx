"use client";

import { useEffect } from "react";

export default function InteractiveBackground() {
  useEffect(() => {
    const canvas = document.getElementById("halftone-canvas") as HTMLCanvasElement | null;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);
    let mouse = { x: width * 0.68, y: height * 0.38, radius: 180 };
    let time = 0;
    let raf = 0;

    const onResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    const onMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    window.addEventListener("resize", onResize);
    window.addEventListener("mousemove", onMouseMove);

    const draw = () => {
      ctx.clearRect(0, 0, width, height);
      time += 0.02;

      const spacing = width < 700 ? 38 : 32;
      const cols = Math.ceil(width / spacing);
      const rows = Math.ceil(height / spacing);

      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          const x = i * spacing + spacing / 2;
          const y = j * spacing + spacing / 2;
          const dist = Math.hypot(mouse.x - x, mouse.y - y);

          let radius = 0.8 + Math.sin(time + i * 0.18 + j * 0.18) * 0.45;

          if (dist < mouse.radius) {
            radius += (1 - dist / mouse.radius) * 2.6;
          }

          ctx.beginPath();
          ctx.arc(x, y, Math.min(radius, 8), 0, Math.PI * 2);
          ctx.fillStyle =
            (i + j) % 3 === 0
              ? `rgba(255, 92, 26, ${0.08 + radius / 24})`
              : `rgba(83, 230, 225, ${0.07 + radius / 24})`;
          ctx.fill();
        }
      }
      raf = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("mousemove", onMouseMove);
    };
  }, []);

  return (
    <>
      <canvas id="halftone-canvas" aria-hidden="true" />
      <div className="bg-halftone-grid" aria-hidden="true" />
      <div className="ambient-lights" aria-hidden="true" />
    </>
  );
}
