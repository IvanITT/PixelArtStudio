import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Konva from "konva";
import { mediaUrl } from "../api/client";
import { Localize } from "../i18n";
import { Icon } from "./Icon";

interface Props {
  src: string;
  alt?: string;
  gridSize?: number;
  className?: string;
  showToolbar?: boolean;
  checker?: boolean;
  onReady?: (info: { width: number; height: number }) => void;
}

export function ImageStage({
  src,
  alt = "",
  gridSize = 1,
  className = "",
  showToolbar = true,
  checker = true,
  onReady,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [grid, setGrid] = useState(false);
  const [fitted, setFitted] = useState(false);

  const url = useMemo(() => mediaUrl(src), [src]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight });
    });
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!url) {
      setImage(null);
      return;
    }
    let alive = true;
    const img = new window.Image();
    img.onload = () => {
      if (alive) {
        setImage(img);
        setFitted(false);
        onReady?.({ width: img.naturalWidth, height: img.naturalHeight });
      }
    };
    img.onerror = () => {
      if (alive) setImage(null);
    };
    img.src = url;
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  const fit = useCallback(() => {
    if (!image || !size.w || !size.h) return;
    const s = Math.min((size.w - 56) / image.naturalWidth, (size.h - 56) / image.naturalHeight);
    const clamped = Math.max(0.05, Math.min(s, 32));
    setScale(clamped);
    setPos({
      x: (size.w - image.naturalWidth * clamped) / 2,
      y: (size.h - image.naturalHeight * clamped) / 2,
    });
    setFitted(true);
  }, [image, size]);

  useEffect(() => {
    if (image && !fitted) fit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [image, size.w, size.h, fitted]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !size.w || !size.h) return;
    const stage = new Konva.Stage({
      container,
      width: size.w,
      height: size.h,
      draggable: true,
    });
    const layer = new Konva.Layer({ listening: false });
    stage.add(layer);

    if (image) {
      const node = new Konva.Image({
        image,
        x: pos.x,
        y: pos.y,
        width: image.naturalWidth * scale,
        height: image.naturalHeight * scale,
        listening: false,
        imageSmoothingEnabled: false,
      });
      layer.add(node);

      if (grid) {
        const step = Math.max(1, gridSize) * scale;
        const stroke = "rgba(255,255,255,0.16)";
        if (step >= 5) {
          const maxLines = 1600;
          let count = 0;
          const x0 = pos.x;
          const y0 = pos.y;
          const w = image.naturalWidth * scale;
          const h = image.naturalHeight * scale;
          for (let x = 0; x <= w && count < maxLines; x += step) {
            layer.add(new Konva.Line({ points: [x0 + x, y0, x0 + x, y0 + h], stroke, strokeWidth: 1, listening: false }));
            count += 1;
          }
          for (let y = 0; y <= h && count < maxLines; y += step) {
            layer.add(new Konva.Line({ points: [x0, y0 + y, x0 + w, y0 + y], stroke, strokeWidth: 1, listening: false }));
            count += 1;
          }
        }
      }
    }

    const onWheel = (e: Konva.KonvaEventObject<WheelEvent>) => {
      e.evt.preventDefault();
      if (!image) return;
      const old = scale;
      const dir = e.evt.deltaY > 0 ? -1 : 1;
      const next = Math.max(0.05, Math.min(old * (dir > 0 ? 1.15 : 0.87), 48));
      const pointer = stage.getPointerPosition();
      if (!pointer) return;
      const mx = (pointer.x - pos.x) / old;
      const my = (pointer.y - pos.y) / old;
      setScale(next);
      setPos({ x: pointer.x - mx * next, y: pointer.y - my * next });
    };
    stage.on("wheel", onWheel);
    stage.on("dragend", () => setPos({ x: stage.x(), y: stage.y() }));
    stage.x(pos.x);
    stage.y(pos.y);
    stage.batchDraw();

    return () => {
      stage.destroy();
    };
  }, [image, size, scale, pos, grid, gridSize]);

  return (
    <Localize>
    <div className={`relative min-h-0 overflow-hidden rounded-lg border border-ink-700 ${checker ? "checker" : "bg-ink-950"} ${className}`}>
      <div
        ref={containerRef}
        className="h-full w-full cursor-grab active:cursor-grabbing"
        role="img"
        aria-label={alt}
      />
      {!image && (
        <div className="absolute inset-0 grid place-items-center text-[11.5px] text-ink-500">
          {src ? "Loading image…" : "No image"}
        </div>
      )}
      {showToolbar && (
        <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 items-center gap-0.5 rounded-lg border border-ink-600 bg-ink-900/90 px-1 py-0.5 text-ink-300 shadow-panel backdrop-blur">
          <button className="rounded p-1 hover:bg-ink-700 hover:text-ink-50" onClick={() => setScale((s) => Math.max(0.05, s * 0.87))} title="Zoom out (-)">
            <Icon name="zoomOut" size={13} />
          </button>
          <span className="w-[52px] text-center font-mono text-[10.5px]">{Math.round(scale * 100)}%</span>
          <button className="rounded p-1 hover:bg-ink-700 hover:text-ink-50" onClick={() => setScale((s) => Math.min(48, s * 1.15))} title="Zoom in (+)">
            <Icon name="zoomIn" size={13} />
          </button>
          <span className="mx-0.5 h-4 w-px bg-ink-700" />
          <button className="rounded p-1 hover:bg-ink-700 hover:text-ink-50" onClick={fit} title="Fit to view (0)">
            <Icon name="fit" size={13} />
          </button>
          <button
            className={`rounded p-1 hover:bg-ink-700 hover:text-ink-50 ${grid ? "text-[rgb(var(--accent))]" : ""}`}
            onClick={() => setGrid((g) => !g)}
            title="Pixel grid (G)"
          >
            <Icon name="grid" size={13} />
          </button>
        </div>
      )}
    </div>
    </Localize>
  );
}
