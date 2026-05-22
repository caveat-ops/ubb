# Post LinkedIn — UBB

---

Certo dia eu quase surtei, bebê.

Tava procurando um post antigo da Mariana e não achava. Fui scrollando, scrollando, scrollando… e percebi duas coisas:

1. Tinha muito conteúdo bom que eu ainda não tinha lido
2. Eu nunca ia dar conta de tudo aquilo

Minha pressão — normalmente 11 por 7 — foi pra 12 por 8. Deu vontade de beber. Peguei uma Corona Cero (recomendo, é perfeita), relaxei, e decidi: vou indexar isso.

Uma pessoa prolífica já é rara. Prolífca **e** profícua, mais ainda. O conteúdo da Mariana merecia ser estruturado como um sistema neural. E se funcionasse pra ela, funcionaria pra qualquer um.

**O que saiu disso:** o UBB (Universal Brain Builder) — um indexador de conteúdo do LinkedIn que suga posts, classifica com IA, organiza em disciplinas de cybersegurança e exibe tudo num grafo de conhecimento interativo.

**Stack:** DeepSeek V4 Pro (vibe coding total), Playwright (extração), Ollama/qwen3 (classificação), FastAPI + Next.js + PostgreSQL + pgvector, Docker.

**O LAB:** uso qualquer ideia como desculpa pra testar IA. Minha meta — como já falei pro Cesar Brod — é escravizar a IA. MVP inicial em menos de 5 minutos. Backend + frontend conectados em ~15. Ajustes finos? Várias horas. No total, uns 2 dias — a IA codando enquanto eu fazia outras coisas (tenho contas pra pagar, amour). Mas confesso: várias horas foram gastas debugando o roteamento com um nginx-proxy legado. O DeepSeek V4 Pro demorou pra perceber o óbvio: expor a API num subdomínio próprio resolveu.

A qualidade vocês avaliam. Pra mim, o experimento é o que conta.

**Links:**
- 🔗 Projeto: github.com/caveat/ubb
- 🧠 Modelo: DeepSeek V4 Pro (ollama)
- 🖥️ TUI: DeepSeek TUI (dica do Akita)
- 🌐 Frontend inicial: Bolt

Be Safe! 🍺

hashtag#vibeCoding hashtag#deepseek hashtag#cyberseguranca hashtag#ia hashtag#openSource hashtag#playwright hashtag#nextjs hashtag#fastapi
