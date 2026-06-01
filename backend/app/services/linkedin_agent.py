import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROFILE_DIR = Path("./.linkedin_browser")


class LinkedInAgent:
    def __init__(self, email: str, password: str, headless: bool = True):
        self.email = email
        self.password = password
        self.headless = headless
        self._invisible = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_browser(self):
        if self.context is not None:
            return

        from invisible_playwright.async_api import InvisiblePlaywright

        for lock in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
            (PROFILE_DIR / lock).unlink(missing_ok=True)

        self._invisible = InvisiblePlaywright(
            headless=self.headless,
            profile_dir=PROFILE_DIR,
            locale="pt-BR",
            timezone="America/Sao_Paulo",
        )
        logger.info("🦊 Iniciando Firefox stealth (primeira execução baixa ~100MB — aguarde)...")
        self.context = await self._invisible.__aenter__()
        logger.info("🦊 Firefox pronto.")

        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
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

        await self.page.wait_for_selector("#username", state="visible", timeout=30000)
        await self.page.fill("#username", self.email)
        await self.page.fill("#password", self.password)
        await self.page.click('[type="submit"]')

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
        self.context = None
