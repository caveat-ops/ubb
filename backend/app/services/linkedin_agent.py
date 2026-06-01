import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROFILE_DIR_CHROMIUM = Path("./.linkedin_browser_chromium")
PROFILE_DIR_FIREFOX  = Path("./.linkedin_browser_firefox")


class LinkedInAgent:
    def __init__(self, email: str, password: str, headless: bool = True, use_firefox: bool = False):
        self.email = email
        self.password = password
        self.headless = headless
        self.use_firefox = use_firefox
        self.profile_dir = PROFILE_DIR_FIREFOX if use_firefox else PROFILE_DIR_CHROMIUM
        self._invisible = None
        self._playwright = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_browser(self):
        if self.context is not None:
            return

        # Firefox usa .parentlock, Chromium usa SingletonLock/Cookie/Socket
        lock_files = (
            [".parentlock"]
            if self.use_firefox
            else ["SingletonLock", "SingletonCookie", "SingletonSocket"]
        )
        for lock in lock_files:
            try:
                (self.profile_dir / lock).unlink(missing_ok=True)
            except PermissionError:
                logger.warning(
                    "Sem permissão para remover %s (profile dir pode pertencer a root/Docker). "
                    "Se o browser falhar, rode: sudo chown -R $USER %s",
                    lock, self.profile_dir,
                )
            except Exception:
                pass

        if self.use_firefox:
            from invisible_playwright.async_api import InvisiblePlaywright
            self._invisible = InvisiblePlaywright(
                headless=self.headless,
                profile_dir=self.profile_dir,
                locale="pt-BR",
                timezone="America/Sao_Paulo",
            )
            logger.info("🦊 Iniciando Firefox stealth (primeira execução baixa ~100MB — aguarde)...")
            self.context = await self._invisible.__aenter__()
            logger.info("🦊 Firefox pronto.")
        else:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self.context = await self._playwright.chromium.launch_persistent_context(
                str(self.profile_dir),
                headless=self.headless,
                viewport={"width": 1280, "height": 720},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'platform', { get: () => 'Linux x86_64' });
                Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en'] });
            """)
            logger.info("🌐 Chrome iniciado.")

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        await self.page.wait_for_timeout(1000)
        logger.info("Browser ready. Initial page URL: %s", self.page.url[:80])

    async def login(self) -> bool:
        await self._ensure_browser()

        # Go directly to login — like the working ainews script
        await self.page.goto(
            "https://www.linkedin.com/login", wait_until="domcontentloaded"
        )

        # If already logged in (persistent context), /login redirects to /feed
        await self.page.wait_for_timeout(3000)
        if self._is_on_feed():
            logger.info("✅ Sessão válida (persistent context)")
            return True

        logger.info("🔑 Fazendo login automático... (URL: %s)", self.page.url[:80])

        # Remove overlay do Google Sign-in que cobre o formulário de email/senha.
        # Identifica divs fixed/absolute de alto z-index que não contêm os inputs de login.
        # Firefox respeita CSP do LinkedIn que bloqueia eval() — o overlay removal é
        # opcional e o login funciona sem ele graças aos seletores robustos.
        try:
            dismissed = await self.page.evaluate("""() => {
                let removed = 0;
                document.querySelectorAll('*').forEach(el => {
                    const s = window.getComputedStyle(el);
                    const z = parseInt(s.zIndex) || 0;
                    if ((s.position === 'fixed' || s.position === 'absolute') && z > 50) {
                        if (!el.querySelector('input[type="email"], input[type="password"]')) {
                            el.style.display = 'none';
                            removed++;
                        }
                    }
                });
                return removed;
            }""")
            if dismissed:
                logger.info("  ↳ %d overlay(s) removido(s)", dismissed)
        except Exception as e:
            logger.warning("  ↳ Overlay removal ignorado (CSP/Firefox): %s", e)
        await self.page.wait_for_timeout(500)

        # LinkedIn alterna entre login single-page (email+senha+botão "Entrar")
        # e two-step (email → Enter → senha). A página atual pode exibir ambos os
        # campos mas com a senha oculta atrás de overlay (ex: "Entrar com Google").
        # Usamos state="attached" + force=True para campos que podem estar cobertos,
        # e tentamos primeiro achar ambos visíveis; fallback para attached.
        username_selectors = [
            'input[autocomplete="username"]',           # 2025-06 (React dynamic IDs)
            'input[autocomplete="username webauthn"]',
            "#username",                                 # seletor clássico (pode voltar)
            'input[name="session_key"]',
            'input[type="email"]',
        ]
        password_selectors = [
            'input[autocomplete="current-password"]',   # 2025-06 (React dynamic IDs)
            "#password",                                 # seletor clássico (pode voltar)
            'input[name="session_password"]',
            'input[type="password"]',
        ]
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Entrar")',
            'button:has-text("Sign in")',
        ]

        async def _find_field(
            selectors: list[str], label: str,
            timeout: int = 5000, state: str = "visible",
        ) -> str | None:
            for sel in selectors:
                try:
                    await self.page.wait_for_selector(sel, state=state, timeout=timeout)
                    logger.info("  ↳ Campo %s encontrado (%s): %s", label, state, sel)
                    return sel
                except Exception:
                    continue
            return None

        # Tenta achar ambos visíveis primeiro (fluxo normal)
        username_field = await _find_field(username_selectors, "email")
        password_field = await _find_field(password_selectors, "senha")

        # Se a senha não está visível (overlay / CSP bloqueou remoção), tenta attached
        if username_field and not password_field:
            logger.info("  ↳ Senha não visível — tentando state=attached (pode estar sob overlay)...")
            password_field = await _find_field(password_selectors, "senha", state="attached")

        if not username_field or not password_field:
            dump_path = Path(".linkedin_login_debug.html")
            dump_path.write_text(await self.page.content(), encoding="utf-8")
            logger.error("❌ Campos de login não encontrados (email=%s, senha=%s). HTML salvo em %s", username_field, password_field, dump_path)
            logger.error("   URL atual: %s | Título: %s", self.page.url, await self.page.title())
            return False

        # LinkedIn pode renderizar 2 formulários no DOM (ex: login principal +
        # Google Sign-in popup). CSP bloqueia eval() no Firefox, então não
        # conseguimos determinar qual formulário está visível.
        #
        # Estratégia: preencher TODOS os inputs de senha com force=True
        # (campos ocultos precisam de force), depois email SEM force
        # (o campo visível não precisa de force, e SEM force o evento React
        # não vaza para outros campos — evita concatenação).
        logger.info("  ↳ Preenchendo campos de senha (force=True, campos podem estar ocultos)...")
        password_inputs = self.page.locator('input[type="password"], input[autocomplete="current-password"]')
        pwd_count = await password_inputs.count()
        for i in range(pwd_count):
            try:
                await password_inputs.nth(i).fill(self.password, force=True, timeout=5000)
            except Exception:
                pass
        logger.info("  ↳ %d senha(s) preenchida(s)", pwd_count)

        # Email SEM force: o campo visível não precisa, e sem force o React
        # não propaga o evento para outros inputs (evita concatenar email na senha).
        logger.info("  ↳ Preenchendo email (sem force, campo visível)...")
        try:
            await self.page.fill(username_field, self.email)
            logger.info("  ↳ Email preenchido sem force")
        except Exception:
            # Fallback: se o seletor visível falhou, tenta todos com force
            logger.info("  ↳ Fallback: force=True nos emails")
            email_inputs = self.page.locator('input[type="email"], input[autocomplete="username"]')
            for i in range(await email_inputs.count()):
                try:
                    await email_inputs.nth(i).fill(self.email, force=True, timeout=5000)
                except Exception:
                    pass

        # Clica no botão Entrar/Sign in se existir; senão Enter no campo de senha
        submit_clicked = False
        for sel in submit_selectors:
            try:
                await self.page.wait_for_selector(sel, state="visible", timeout=2000)
                await self.page.click(sel)
                logger.info("  ↳ Botão submit clicado: %s", sel)
                submit_clicked = True
                break
            except Exception:
                continue
        if not submit_clicked:
            await self.page.keyboard.press("Enter")

        try:
            await self.page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass

        if self._is_on_feed():
            logger.info("✅ Login automático bem-sucedido")
            return True

        if self._is_on_checkpoint():
            logger.warning(
                "⚠️ LinkedIn pediu verificação. "
                "Notificação chegou no celular? Aprove e o script continua..."
            )
            for _ in range(150):
                await self.page.wait_for_timeout(2000)
                # Page auto-redirects to feed once user approves on phone
                if self._is_on_feed():
                    logger.info("✅ Verificação concluída!")
                    return True
            logger.warning("Timeout aguardando verificação do LinkedIn (5 min)")
            return False

        logger.error("Login falhou — URL: %s", self.page.url[:80])
        return False

    async def extract_feed_posts_no_eval(self) -> list[dict]:
        """Extrai posts de .feed-shared-update-v2 sem usar page.evaluate().
        Usa apenas a API de locators do Playwright — compatível com Firefox+CSP."""
        posts = []
        containers = self.page.locator('.feed-shared-update-v2')
        count = await containers.count()
        for i in range(count):
            try:
                c = containers.nth(i)
                # Link
                link = None
                for link_sel in [
                    'a[href*="/posts/"]', 'a[href*="activity-"]',
                    'a[href*="/feed/update/"]', 'a[data-urn*="activity"]',
                ]:
                    el = c.locator(link_sel).first
                    if await el.count():
                        href = await el.get_attribute("href")
                        if href:
                            link = href if href.startswith("http") else f"https://www.linkedin.com{href}"
                            break
                if not link:
                    continue
                # Texto
                text = ""
                for text_sel in [
                    '.feed-shared-text__text-visual', '.feed-shared-text',
                    '.feed-shared-update-v2__description', '.update-components-text',
                    '.feed-shared-inline-show-more-text',
                ]:
                    try:
                        el = c.locator(text_sel).first
                        if await el.count():
                            text = (await el.text_content() or "").strip()
                            if text:
                                break
                    except Exception:
                        continue
                if not text:
                    continue
                # Data
                date = ""
                try:
                    time_el = c.locator("time").first
                    if await time_el.count():
                        date = (await time_el.get_attribute("datetime")) or ""
                        if not date:
                            date = (await time_el.text_content() or "").strip()
                except Exception:
                    pass
                # Hashtags
                hashtags = re.findall(r"#(\w+)", text)
                posts.append({
                    "link": link,
                    "content": text,
                    "date": date,
                    "hashtags": hashtags,
                })
            except Exception as e:
                logger.debug("Erro extraindo post %d: %s", i, e)
        return posts

    async def get_viewport_size_no_eval(self) -> dict:
        """Retorna viewport size sem eval. Page.viewport_size já é nativo."""
        return self.page.viewport_size or {"width": 1280, "height": 720}

    async def scroll_page_no_eval(self, delta_y: int = 0):
        """Scrolla a página — keyboard/mouse, sem eval()."""
        if delta_y:
            await self.page.mouse.wheel(0, delta_y)
        else:
            await self.page.keyboard.press("End")

    def _is_on_feed(self) -> bool:
        return bool(re.search(r"linkedin\.com/(feed|home)", self.page.url))

    def _is_on_checkpoint(self) -> bool:
        return bool(re.search(r"/(login|authwall|checkpoint|check)", self.page.url))

    async def get_recent_posts(
        self, url: str, max_posts: int = 20
    ) -> list[dict]:
        await self._ensure_browser()

        await self.page.goto(url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(3000)

        current_url = self.page.url
        if "authwall" in current_url:
            logger.error(
                "LinkedIn authwall — sessão expirada. "
                "Rode com PLAYWRIGHT_HEADLESS=false uma vez para renovar."
            )
            return []

        logger.info("URL após navegação: %s", current_url[:100])

        posts = []
        seen_urls: set[str] = set()
        last_height = 0
        stale_scrolls = 0
        max_stale_scrolls = 10

        while len(posts) < max_posts and stale_scrolls < max_stale_scrolls:
            extracted = await self._extract_posts()
            for post in extracted:
                url_key = post["linkedin_url"]
                if url_key and url_key not in seen_urls:
                    seen_urls.add(url_key)
                    posts.append(post)
                    if len(posts) >= max_posts:
                        break

            new_height = await self.page.evaluate(
                "document.body.scrollHeight"
            )
            if new_height == last_height:
                stale_scrolls += 1
            else:
                stale_scrolls = 0
            last_height = new_height

            await self.page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )
            await self.page.wait_for_timeout(2000)

        if not posts:
            body_text = await self.page.evaluate(
                "document.body.innerText.substring(0, 500)"
            )
            logger.info(
                "Preview da página: %s", body_text[:200].replace("\n", " ")
            )

        logger.info("Extraídos %d posts de %s", len(posts), url)
        return posts[:max_posts]

    async def _extract_posts(self) -> list[dict]:
        posts = []

        selectors = [
            ".feed-shared-update-v2",
            ".occludable-update",
            ".profile-activity-card",
            ".update-components-actor",
            "li[data-urn]",
            "article",
            "div[data-urn]",
        ]
        post_containers = []
        for sel in selectors:
            els = await self.page.query_selector_all(sel)
            if els:
                logger.info("Found %d posts with selector '%s'", len(els), sel)
                post_containers = els
                break

        if not post_containers:
            title = await self.page.title()
            logger.info(
                "No post selectors matched. Page title: %s, URL: %s",
                title, self.page.url[:80],
            )

        for container in post_containers:
            try:
                post = await self._extract_single_post(container)
                if post and post.get("linkedin_url"):
                    posts.append(post)
            except Exception as e:
                logger.debug("Error extracting post: %s", e)

        return posts

    async def _extract_single_post(self, container) -> Optional[dict]:
        link = await container.query_selector(
            "a[href*='/posts/'], a[href*='/feed/update/']"
        )
        if not link:
            link = await container.query_selector(
                "a[href*='activity-']"
            )
        if not link:
            link = await container.query_selector(
                "a[href*='urn:li:activity']"
            )
        if not link:
            link = await container.query_selector(
                "a[data-urn*='activity']"
            )
        if not link:
            return None

        href = await link.get_attribute("href")
        if not href:
            return None

        post_url = (
            href
            if href.startswith("http")
            else f"https://www.linkedin.com{href}"
        )
        post_id = self._extract_post_id(post_url)

        content = ""
        for sel in [
            ".feed-shared-text__text-visual",
            ".update-components-text",
            ".break-words",
            ".profile-activity-card__content",
            ".update-components-text-relative",
            "span[dir='ltr']",
            "p",
        ]:
            el = await container.query_selector(sel)
            if el:
                text = await el.text_content()
                if text:
                    content = text.strip()
                    break

        post_date = ""
        time_el = await container.query_selector("time")
        if time_el:
            dt = await time_el.get_attribute("datetime")
            if dt:
                post_date = dt
            else:
                txt = await time_el.text_content()
                if txt:
                    post_date = txt.strip()

        hashtags = re.findall(r"#(\w+)", content) if content else []

        images = []
        img_els = await container.query_selector_all(
            "img.feed-shared-image__image, img.update-components-image__image"
        )
        for img in img_els:
            src = await img.get_attribute("src")
            if src and src.startswith("https"):
                images.append(src)

        return {
            "linkedin_url": post_url,
            "linkedin_post_id": post_id,
            "content": content,
            "post_date": post_date,
            "hashtags": hashtags,
            "images": images,
        }

    def _extract_post_id(self, url: str) -> str:
        m = re.search(r"activity[_-](\d+)", url)
        if m:
            return m.group(1)
        m = re.search(r"urn:li:activity:(\d+)", url)
        if m:
            return m.group(1)
        return url.rstrip("/").split("/")[-1] if url else ""

    async def close(self):
        if self._invisible is not None:
            await self._invisible.__aexit__(None, None, None)
            self._invisible = None
        if self._playwright is not None:
            await self.context.close()
            await self._playwright.stop()
            self._playwright = None
        self.context = None
