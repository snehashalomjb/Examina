"use client";

/**
 * Examiner/admin side of one candidate's live video.
 *
 * Opens a signaling socket for exactly one exam session, waits for that candidate's
 * browser to offer its camera, answers, and exposes the resulting `MediaStream` plus an
 * honest connection state so the UI never has to guess whether what it is showing is
 * actually live.
 *
 * One instance per candidate tile. Mounting only while a tile is on screen (the caller's
 * job - a modal or a visible grid card) keeps peer-connection count matched to what an
 * examiner is actually watching, not every session that merely exists.
 */

import { useEffect, useRef, useState } from "react";

import { API_BASE, tokens } from "@/lib/api";

const WS_SUBPROTOCOL = "exam-live-signal.v1";
const ICE_SERVERS: RTCIceServer[] = [{ urls: "stun:stun.l.google.com:19302" }];

export type LiveViewState =
  | "connecting"
  | "waiting-for-candidate"
  | "connected"
  | "reconnecting"
  | "unavailable";

type SignalMessage = {
  type: "welcome" | "candidate-online" | "candidate-offline" | "offer" | "ice-candidate";
  viewer_id?: string;
  candidate_online?: boolean;
  sdp?: RTCSessionDescriptionInit;
  candidate?: RTCIceCandidateInit;
};

export function useLiveView(sessionId: string | null, enabled: boolean) {
  const [state, setState] = useState<LiveViewState>("connecting");
  const [stream, setStream] = useState<MediaStream | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const viewerIdRef = useRef<string | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const retries = useRef(0);
  const stoppedRef = useRef(false);

  function send(message: Record<string, unknown>) {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message));
    }
  }

  async function handle(message: SignalMessage) {
    switch (message.type) {
      case "welcome": {
        if (message.viewer_id) viewerIdRef.current = message.viewer_id;
        retries.current = 0;
        setState(message.candidate_online ? "connecting" : "waiting-for-candidate");
        break;
      }
      case "candidate-online": {
        setState("connecting");
        break;
      }
      case "candidate-offline": {
        peerRef.current?.close();
        peerRef.current = null;
        setStream(null);
        setState("waiting-for-candidate");
        break;
      }
      case "offer": {
        if (!message.sdp) return;
        peerRef.current?.close();
        const peer = new RTCPeerConnection({ iceServers: ICE_SERVERS });
        peerRef.current = peer;

        peer.ontrack = (event) => {
          setStream(event.streams[0] ?? null);
          setState("connected");
        };
        peer.onicecandidate = (event) => {
          if (event.candidate) {
            send({ type: "ice-candidate", candidate: event.candidate.toJSON() });
          }
        };
        peer.onconnectionstatechange = () => {
          if (peer.connectionState === "failed" || peer.connectionState === "disconnected") {
            setState("reconnecting");
            setStream(null);
          } else if (peer.connectionState === "closed") {
            setStream(null);
          }
        };

        await peer.setRemoteDescription(message.sdp);
        const answer = await peer.createAnswer();
        await peer.setLocalDescription(answer);
        send({ type: "answer", sdp: answer });
        break;
      }
      case "ice-candidate": {
        if (message.candidate && peerRef.current) {
          try {
            await peerRef.current.addIceCandidate(message.candidate);
          } catch {
            /* a stray candidate after renegotiation is not worth surfacing */
          }
        }
        break;
      }
    }
  }

  function scheduleReconnect(id: string) {
    if (stoppedRef.current) return;
    const delay = Math.min(20_000, 1_500 * 2 ** retries.current);
    retries.current += 1;
    reconnectTimer.current = window.setTimeout(() => connect(id), delay);
  }

  function connect(id: string) {
    if (stoppedRef.current) return;
    const access = tokens.access();
    if (!access) {
      setState("unavailable");
      return;
    }

    const url = `${API_BASE.replace(/^http/, "ws")}/ws/sessions/${id}/live-view`;
    let socket: WebSocket;
    try {
      socket = new WebSocket(url, [WS_SUBPROTOCOL, access]);
    } catch {
      scheduleReconnect(id);
      return;
    }
    socketRef.current = socket;

    socket.onmessage = (event) => {
      let message: SignalMessage;
      try {
        message = JSON.parse(event.data as string);
      } catch {
        return;
      }
      void handle(message);
    };

    socket.onclose = () => {
      socketRef.current = null;
      if (stoppedRef.current) return;
      setState((current) => (current === "connected" ? "reconnecting" : current));
      scheduleReconnect(id);
    };
    socket.onerror = () => {
      // onclose always follows; the reconnect is scheduled there.
    };
  }

  function teardown() {
    if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
    peerRef.current?.close();
    peerRef.current = null;
    socketRef.current?.close(1000, "Left monitoring");
    socketRef.current = null;
    viewerIdRef.current = null;
  }

  useEffect(() => {
    if (!sessionId || !enabled) {
      setState("connecting");
      setStream(null);
      return;
    }

    stoppedRef.current = false;
    setState("connecting");
    setStream(null);
    connect(sessionId);

    return () => {
      stoppedRef.current = true;
      teardown();
      setStream(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, enabled]);

  return { state, stream };
}
