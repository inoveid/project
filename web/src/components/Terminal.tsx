import { useCallback, useEffect, useRef } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";
import { useTerminal, type TerminalStatus } from "../hooks/useTerminal";

interface TerminalProps {
  productId: string;
  visible: boolean;
}

function StatusDot({ status }: { status: TerminalStatus }) {
  const colors: Record<TerminalStatus, string> = {
    disconnected: "bg-red-500",
    connecting: "bg-yellow-400 animate-pulse",
    connected: "bg-green-500",
  };
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status]}`} />;
}

export function TerminalPanel({ productId, visible }: TerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const initializedRef = useRef(false);
  const lastSizeRef = useRef<{ cols: number; rows: number }>({ cols: 0, rows: 0 });
  const connectedAtRef = useRef(0);

  console.log("[Terminal] render, visible:", visible, "productId:", productId, "initialized:", initializedRef.current);

  const handleData = useCallback((data: string) => {
    console.log("[Terminal] handleData called, len:", data.length, "xterm exists:", !!xtermRef.current);
    xtermRef.current?.write(data);
  }, []);

  const { status, send, resize, reconnect } = useTerminal({
    productId,
    enabled: visible,
    onData: handleData,
  });

  // Track connection time to suppress early resizes
  useEffect(() => {
    if (status === "connected") {
      console.log("[Terminal] status=connected, setting connectedAt");
      connectedAtRef.current = Date.now();
    }
  }, [status]);

  // Initialize xterm
  useEffect(() => {
    console.log("[Terminal] init effect, visible:", visible, "container:", !!containerRef.current, "initialized:", initializedRef.current);
    if (!visible || !containerRef.current || initializedRef.current) return;

    console.log("[Terminal] creating xterm instance");
    const term = new XTerm({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Menlo, monospace",
      theme: {
        background: "#1a1b26",
        foreground: "#c0caf5",
        cursor: "#c0caf5",
        selectionBackground: "#33467c",
        black: "#15161e",
        red: "#f7768e",
        green: "#9ece6a",
        yellow: "#e0af68",
        blue: "#7aa2f7",
        magenta: "#bb9af7",
        cyan: "#7dcfff",
        white: "#a9b1d6",
      },
      scrollback: 5000,
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(webLinksAddon);
    term.open(containerRef.current);
    console.log("[Terminal] xterm opened in container");

    // Fit after open
    requestAnimationFrame(() => {
      fitAddon.fit();
      lastSizeRef.current = { cols: term.cols, rows: term.rows };
      console.log("[Terminal] initial fit:", term.cols, "x", term.rows);
    });

    // Send user input to PTY
    term.onData((data) => {
      console.log("[Terminal] term.onData fired, data:", JSON.stringify(data), "calling send()");
      send(data);
    });

    xtermRef.current = term;
    fitAddonRef.current = fitAddon;
    initializedRef.current = true;

    // Focus terminal so keyboard input works
    term.focus();
    console.log("[Terminal] focused, hasFocus:", term.textarea?.ownerDocument.activeElement === term.textarea);

    return () => {
      console.log("[Terminal] cleanup, disposing xterm");
      term.dispose();
      xtermRef.current = null;
      fitAddonRef.current = null;
      initializedRef.current = false;
    };
  }, [visible, send]);

  // Handle resize
  useEffect(() => {
    if (!visible || !fitAddonRef.current) return;

    const handleResize = () => {
      const fitAddon = fitAddonRef.current;
      const term = xtermRef.current;
      if (!fitAddon || !term) return;

      fitAddon.fit();

      const { cols, rows } = term;
      const last = lastSizeRef.current;

      if (cols === last.cols && rows === last.rows) {
        console.log("[Terminal] resize skipped — same size:", cols, "x", rows);
        return;
      }

      if (Date.now() - connectedAtRef.current < 500) {
        console.log("[Terminal] resize suppressed (early after connect):", cols, "x", rows);
        lastSizeRef.current = { cols, rows };
        return;
      }

      console.log("[Terminal] resize sending:", cols, "x", rows);
      lastSizeRef.current = { cols, rows };
      resize(cols, rows);
    };

    const timer = setTimeout(handleResize, 50);

    const container = containerRef.current;
    if (!container) return () => clearTimeout(timer);

    let resizeTimeout: ReturnType<typeof setTimeout>;
    const observer = new ResizeObserver(() => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(handleResize, 100);
    });
    observer.observe(container);

    return () => {
      clearTimeout(timer);
      clearTimeout(resizeTimeout);
      observer.disconnect();
    };
  }, [visible, resize]);

  // Focus terminal when clicking on it
  const handleContainerClick = useCallback(() => {
    console.log("[Terminal] container clicked, focusing xterm");
    xtermRef.current?.focus();
  }, []);

  if (!visible) return null;

  return (
    <div className="flex flex-col h-full bg-[#1a1b26]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#1a1b26] border-b border-gray-700 shrink-0">
        <div className="flex items-center gap-2">
          <StatusDot status={status} />
          <span className="text-xs text-gray-400">Terminal</span>
        </div>
        {status === "disconnected" && (
          <button
            onClick={reconnect}
            className="text-[11px] text-blue-400 hover:text-blue-300"
          >
            Reconnect
          </button>
        )}
      </div>
      <div
        ref={containerRef}
        className="flex-1 min-h-0"
        onClick={handleContainerClick}
      />
    </div>
  );
}
