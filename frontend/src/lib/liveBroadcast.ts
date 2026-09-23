/**
 * Candidate-side WebRTC broadcaster.
 *
 * Offers the exam tab's own camera stream - the same `MediaStream` `ProctorEngine`
 * already opened for vision inference, not a second `getUserMedia()` call - to any
 * number of staff watching this session live. One `RTCPeerConnection` per viewer: a
 * mesh, not an SFU, because a handful of invigilators on a handful of candidates is the
 * scale this exists for.
 *
 * The server (`app.services.live_signal`) never touches media, only relays the small
 * JSON control messages below between this class and `useLiveView` on the examiner side.
 */

import { API_BASE, tokens } from "@/lib/api";

/** Must match WS_SUBPROTOCOL in backend/app/api/v1/live_signal.py. */
const WS_SUBPROTOCOL = "exam-live-signal.v1";

/** Public STUN only - no TURN relay is configured for this deployment, so a peer behind
 * a symmetric NAT may fail to connect. That shows up honestly as "reconnecting" rather
 * than silently failing, which is the whole point of surfacing connection state at all. */
const ICE_SERVERS: RTCIceServer[] = [{ urls: "stun:stun.l.google.com:19302" }];

type SignalMessage = {
  type: "welcome" | "viewer-join" | "viewer-leave" | "offer" | "answer" | "ice-candidate";
  viewer_id?: string;
  sdp?: RTCSessionDescriptionInit;
  candidate?: RTCIceCandidateInit;
};

export class LiveBroadcaster {
  private sessionId: string;
  private examToken: string;
  private stream: MediaStream;
  private socket: WebSocket | null = null;
  private peers = new Map<string, RTCPeerConnection>();
  private stopped = false;
  private reconnectTimer: number | null = null;
  private retries = 0;

  constructor(options: { sessionId: string; examToken: string; stream: MediaStream }) {
    this.sessionId = options.sessionId;
    this.examToken = options.examToken;
    this.stream = options.stream;
  }

  /** A fresh exam token is issued on every heartbeat - kept in step the same way
   * ProctorEngine.setExamToken is, though this socket only needs it at connect time. */
  setExamToken(token: string) {
    this.examToken = token;
  }

  start() {
    if (this.stopped) return;
    this.connect();
  }

  private connect() {
    if (this.stopped || this.socket) return;
    const access = tokens.access();
    if (!access) return;

    const url = `${API_BASE.replace(/^http/, "ws")}/ws/sessions/${this.sessionId}/live-broadcast`;
    let socket: WebSocket;
    try {
      socket = new WebSocket(url, [WS_SUBPROTOCOL, access, this.examToken]);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;

    socket.onopen = () => {
      this.retries = 0;
    };

    socket.onmessage = (event) => {
      let message: SignalMessage;
      try {
        message = JSON.parse(event.data as string);
      } catch {
        return;
      }
      void this.handle(message);
    };

    socket.onclose = () => {
      this.socket = null;
      this.scheduleReconnect();
    };
    socket.onerror = () => {
      // onclose always follows; the reconnect is scheduled there.
    };
  }

  private scheduleReconnect() {
    if (this.stopped) return;
    const delay = Math.min(30_000, 2_000 * 2 ** this.retries);
    this.retries += 1;
    this.reconnectTimer = window.setTimeout(() => this.connect(), delay);
  }

  private send(message: Record<string, unknown>) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  private async handle(message: SignalMessage) {
    switch (message.type) {
      case "viewer-join": {
        if (message.viewer_id) await this.offerTo(message.viewer_id);
        break;
      }
      case "viewer-leave": {
        if (message.viewer_id) this.closePeer(message.viewer_id);
        break;
      }
      case "answer": {
        if (message.viewer_id && message.sdp) {
          const peer = this.peers.get(message.viewer_id);
          await peer?.setRemoteDescription(message.sdp);
        }
        break;
      }
      case "ice-candidate": {
        if (message.viewer_id && message.candidate) {
          const peer = this.peers.get(message.viewer_id);
          try {
            await peer?.addIceCandidate(message.candidate);
          } catch {
            /* a stray candidate after the peer closed is not an error worth surfacing */
          }
        }
        break;
      }
    }
  }

  private async offerTo(viewerId: string) {
    this.closePeer(viewerId); // a re-join (examiner refreshed) replaces any stale peer

    const peer = new RTCPeerConnection({ iceServers: ICE_SERVERS });
    this.peers.set(viewerId, peer);
    this.stream.getTracks().forEach((track) => peer.addTrack(track, this.stream));

    peer.onicecandidate = (event) => {
      if (event.candidate) {
        this.send({ type: "ice-candidate", viewer_id: viewerId, candidate: event.candidate.toJSON() });
      }
    };
    peer.onconnectionstatechange = () => {
      if (peer.connectionState === "failed" || peer.connectionState === "closed") {
        this.closePeer(viewerId);
      }
    };

    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);
    this.send({ type: "offer", viewer_id: viewerId, sdp: offer });
  }

  private closePeer(viewerId: string) {
    const peer = this.peers.get(viewerId);
    if (peer) {
      peer.onicecandidate = null;
      peer.onconnectionstatechange = null;
      peer.close();
      this.peers.delete(viewerId);
    }
  }

  stop() {
    if (this.stopped) return;
    this.stopped = true;
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);
    this.peers.forEach((_peer, viewerId) => this.closePeer(viewerId));
    this.socket?.close(1000, "Session ended");
    this.socket = null;
  }
}
