export interface Env {
  BOT_NAME: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return Response.json({
        ok: true,
        service: env.BOT_NAME || "PaperclipMaxxer",
        note: "The Python Discord gateway bot must be running separately.",
      });
    }

    return new Response("PaperclipMaxxer health worker. Try /health.\n", {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  },
};

