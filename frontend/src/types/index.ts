export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export interface SSEMetadata {
  conversation_id: string;
}

export interface SSEToken {
  content: string;
  node: string;
}

export interface SSEDone {
  status: string;
}

export interface SSEValidation {
  warnings: string[];
}

export interface StreamCallbacks {
  onMetadata: (data: SSEMetadata) => void;
  onToken: (data: SSEToken) => void;
  onDone: (data: SSEDone) => void;
  onValidation: (data: SSEValidation) => void;
  onError: (error: Error) => void;
}
