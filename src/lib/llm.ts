import OpenAI from "openai";
import Anthropic from "@anthropic-ai/sdk";
import { GoogleGenerativeAI } from "@google/generative-ai";
import axios from "axios";

export type LLMProvider = "openai" | "anthropic" | "google" | "openrouter";

export interface LLMMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface LLMConfig {
  provider: LLMProvider;
  model: string;
  apiKey: string;
}

export async function callLLM(config: LLMConfig, messages: LLMMessage[]) {
  const { provider, model, apiKey } = config;

  switch (provider) {
    case "openai":
      const openai = new OpenAI({ apiKey });
      const oaResponse = await openai.chat.completions.create({
        model,
        messages: messages.map((m) => ({ role: m.role, content: m.content })),
      });
      return oaResponse.choices[0].message.content || "";

    case "anthropic":
      const anthropic = new Anthropic({ apiKey });
      const systemMessage = messages.find((m) => m.role === "system")?.content;
      const userMessages = messages.filter((m) => m.role !== "system");
      const antResponse = await anthropic.messages.create({
        model,
        max_tokens: 1024,
        system: systemMessage,
        messages: userMessages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        })),
      });
      return antResponse.content[0].type === "text" ? antResponse.content[0].text : "";

    case "google":
      const genAI = new GoogleGenerativeAI(apiKey);
      const googleModel = genAI.getGenerativeModel({ model });
      const systemPrompt = messages.find((m) => m.role === "system")?.content || "";
      const chat = googleModel.startChat({
        history: messages
          .filter((m) => m.role !== "system")
          .slice(0, -1)
          .map((m) => ({
            role: m.role === "user" ? "user" : "model",
            parts: [{ text: m.content }],
          })),
      });
      const lastMessage = messages[messages.length - 1].content;
      const result = await chat.sendMessage(`${systemPrompt}\n\n${lastMessage}`);
      return result.response.text();

    case "openrouter":
      const response = await axios.post(
        "https://openrouter.ai/api/v1/chat/completions",
        {
          model,
          messages,
        },
        {
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "HTTP-Referer": process.env.NEXT_PUBLIC_API_URL || "http://localhost:3000",
            "X-Title": "Lirox",
          },
        }
      );
      return response.data.choices[0].message.content || "";

    default:
      throw new Error(`Unsupported provider: ${provider}`);
  }
}
