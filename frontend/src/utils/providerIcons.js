import { Bot, Sparkles, Cpu, KeyRound, Mail, Send, Server, Inbox } from "lucide-react";

const ICONS = {
  openai: Sparkles,
  anthropic: Bot,
  google: Sparkles,
  azure_openai: Cpu,
  mistral: Cpu,
  cohere: Cpu,
  custom_llm: KeyRound,
  gmail: Mail,
  outlook: Send,
  smtp: Server,
  imap: Inbox,
};

export function providerIcon(provider) {
  return ICONS[provider] || KeyRound;
}
