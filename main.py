#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KataBump 服务器续期脚本 - GitHub Actions 版本 (v1.0)

核心特性：
- 使用 curl_cffi 模拟真实浏览器 TLS 指纹，绕过 Cloudflare 检测
- 先通过 API 登录获取 Cookie，再同步到 DrissionPage 浏览器
- 适配 GitHub Actions 环境，无需浏览器插件
- 借鉴 linuxdo-checkin 项目的成功方案

环境变量：
- KB_EMAIL: KataBump 账号邮箱
- KB_PASSWORD: KataBump 账号密码
- KB_RENEW_URL: 续期页面 URL (如 https://dashboard.katabump.com/servers/edit?id=xxxxx)
- TELEGRAM_TOKEN: (可选) Telegram Bot Token
- TELEGRAM_USERID: (可选) Telegram 用户 ID
"""

import os
import re
import sys
import time
import random
import functools
from loguru import logger
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup

# 移除可能干扰浏览器的环境变量
os.environ.pop("DISPLAY", None)
os.environ.pop("DYLD_LIBRARY_PATH", None)

# 环境变量
KB_EMAIL = os.environ.get("KB_EMAIL", "")
KB_PASSWORD = os.environ.get("KB_PASSWORD", "")
KB_RENEW_URL = os.environ.get("KB_RENEW_URL", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_USERID = os.environ.get("TELEGRAM_USERID", "")

# URL 常量
BASE_URL = "https://dashboard.katabump.com"
LOGIN_URL = f"{BASE_URL}/auth/login"
DASHBOARD_URL = f"{BASE_URL}/dashboard"


def retry_decorator(retries=3, delay=2):
    """重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        logger.error(f"函数 {func.__name__} 最终执行失败: {str(e)}")
                        raise
                    logger.warning(f"函数 {func.__name__} 第 {attempt + 1}/{retries} 次尝试失败: {str(e)}")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator


def send_telegram(message: str, success: bool = True):
    """发送 Telegram 通知"""
    if not TELEGRAM_TOKEN or not TELEGRAM_USERID:
        logger.info("未配置 Telegram，跳过通知")
        return
    
    emoji = "✅" if success else "❌"
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_USERID,
            "parse_mode": "HTML",
            "text": f"{emoji} <b>KataBump</b> {message}"
        }
        resp = cffi_requests.post(url, data=data, timeout=10, impersonate="chrome136")
        if resp.status_code == 200:
            logger.success("Telegram 通知发送成功")
        else:
            logger.warning(f"Telegram 通知发送失败: {resp.status_code}")
    except Exception as e:
        logger.error(f"Telegram 通知异常: {e}")


class KataBumpRenewer:
    def __init__(self):
        self.session = cffi_requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        })
        self.browser = None
        self.page = None
    
    def _init_browser(self):
        """初始化 DrissionPage 浏览器"""
        from DrissionPage import ChromiumOptions, Chromium
        from sys import platform
        
        if platform == "linux" or platform == "linux2":
            platform_id = "X11; Linux x86_64"
        elif platform == "darwin":
            platform_id = "Macintosh; Intel Mac OS X 10_15_7"
        elif platform == "win32":
            platform_id = "Windows NT 10.0; Win64; x64"
        else:
            platform_id = "X11; Linux x86_64"
        
        co = (
            ChromiumOptions()
            .headless(True)
            .incognito(True)
            .set_argument("--no-sandbox")
            .set_argument("--disable-gpu")
            .set_argument("--disable-dev-shm-usage")
            .set_argument("--disable-blink-features=AutomationControlled")
            .set_argument("--window-size=1920,1080")
        )
        co.set_user_agent(
            f"Mozilla/5.0 ({platform_id}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        
        self.browser = Chromium(co)
        self.page = self.browser.new_tab()
        logger.info("浏览器初始化完成")
    
    def _sync_cookies_to_browser(self):
        """将 session cookies 同步到浏览器"""
        cookies_dict = self.session.cookies.get_dict()
        dp_cookies = []
        for name, value in cookies_dict.items():
            dp_cookies.append({
                "name": name,
                "value": value,
                "domain": ".katabump.com",
                "path": "/",
            })
        
        # 先访问一下网站以设置 cookie 域
        self.page.get(BASE_URL)
        time.sleep(2)
        self.page.set.cookies(dp_cookies)
        logger.info(f"已同步 {len(dp_cookies)} 个 Cookie 到浏览器")
    
    @retry_decorator(retries=3)
    def login_via_api(self) -> bool:
        """通过 API 登录获取 Cookie"""
        logger.info("开始 API 登录...")
        
        # 先访问登录页获取必要的 token
        resp = self.session.get(LOGIN_URL, impersonate="chrome136")
        if resp.status_code != 200:
            logger.error(f"访问登录页失败: {resp.status_code}")
            return False
        
        # 解析页面获取 CSRF token (如果有)
        soup = BeautifulSoup(resp.text, "html.parser")
        csrf_input = soup.find("input", {"name": "_token"})
        csrf_token = csrf_input.get("value") if csrf_input else None
        
        # 构建登录数据
        login_data = {
            "email": KB_EMAIL,
            "password": KB_PASSWORD,
        }
        if csrf_token:
            login_data["_token"] = csrf_token
            logger.info(f"获取到 CSRF Token: {csrf_token[:20]}...")
        
        # 发送登录请求
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": BASE_URL,
            "Referer": LOGIN_URL,
        }
        
        resp = self.session.post(
            LOGIN_URL,
            data=login_data,
            headers=headers,
            impersonate="chrome136",
            allow_redirects=True
        )
        
        # 检查登录结果
        if resp.status_code == 200 and ("dashboard" in resp.url or "login" not in resp.url):
            logger.success("API 登录成功!")
            return True
        
        # 检查响应内容
        if "dashboard" in resp.text.lower() or "servers" in resp.text.lower():
            logger.success("API 登录成功 (通过响应内容判断)")
            return True
        
        logger.error(f"API 登录失败，状态码: {resp.status_code}, URL: {resp.url}")
        return False
    
    @retry_decorator(retries=3)
    def check_server_status(self) -> dict:
        """检查服务器状态"""
        logger.info("检查服务器状态...")
        
        resp = self.session.get(KB_RENEW_URL, impersonate="chrome136")
        if resp.status_code != 200:
            logger.error(f"访问续期页面失败: {resp.status_code}")
            return None
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 提取服务器信息
        info = {}
        
        # 查找服务器名称
        title = soup.find("h5", class_="card-title")
        if title:
            info["name"] = title.get_text(strip=True)
        
        # 查找到期时间
        expire_text = soup.find(string=re.compile(r"Expire|expire|到期", re.I))
        if expire_text:
            info["expire"] = expire_text.parent.get_text(strip=True) if expire_text.parent else str(expire_text)
        
        logger.info(f"服务器信息: {info}")
        return info
    
    def renew_via_browser(self) -> bool:
        """通过浏览器完成续期（处理 Turnstile 验证）"""
        logger.info("开始浏览器续期流程...")
        
        self._init_browser()
        self._sync_cookies_to_browser()
        
        # 访问续期页面
        logger.info(f"访问续期页面: {KB_RENEW_URL}")
        self.page.get(KB_RENEW_URL)
        time.sleep(3)
        
        # 检查是否需要重新登录
        if "login" in self.page.url:
            logger.warning("Cookie 同步后仍需登录，尝试浏览器登录...")
            return self._browser_login_and_renew()
        
        return self._do_renew()
    
    def _browser_login_and_renew(self) -> bool:
        """浏览器登录并续期"""
        logger.info("执行浏览器登录...")
        
        try:
            # 填写登录表单
            email_input = self.page.ele('css:input[type="email"], input[name="email"], input#email', timeout=5)
            password_input = self.page.ele('css:input[type="password"], input[name="password"], input#password', timeout=5)
            submit_btn = self.page.ele('css:button[type="submit"], button#submit', timeout=5)
            
            if email_input and password_input and submit_btn:
                email_input.input(KB_EMAIL)
                time.sleep(0.5)
                password_input.input(KB_PASSWORD)
                time.sleep(0.5)
                submit_btn.click()
                logger.info("已提交登录表单")
                time.sleep(5)
            else:
                logger.error("找不到登录表单元素")
                return False
            
            # 检查登录结果
            if "login" in self.page.url:
                logger.error("登录失败，仍在登录页")
                return False
            
            # 跳转到续期页面
            self.page.get(KB_RENEW_URL)
            time.sleep(3)
            
            return self._do_renew()
            
        except Exception as e:
            logger.error(f"浏览器登录异常: {e}")
            return False
    
    def _do_renew(self) -> bool:
        """执行续期操作"""
        logger.info("查找 Renew 按钮...")
        
        # 查找 Renew 按钮
        renew_btn = self.page.ele('css:button[data-bs-toggle="modal"][data-bs-target="#renew-modal"]', timeout=10)
        if not renew_btn:
            renew_btn = self.page.ele('text:Renew', timeout=5)
        
        if not renew_btn:
            logger.error("未找到 Renew 按钮")
            return False
        
        # 滚动到按钮并点击
        try:
            renew_btn.scroll.to_see()
            time.sleep(1)
        except:
            pass
        
        renew_btn.click()
        logger.info("已点击 Renew 按钮，等待弹窗...")
        time.sleep(3)
        
        # 等待 Turnstile 验证
        return self._wait_turnstile_and_submit()
    
    def _wait_turnstile_and_submit(self) -> bool:
        """等待 Turnstile 验证并提交"""
        logger.info("等待 Turnstile 验证...")
        
        max_wait = 120  # 最多等待 120 秒
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                # 检查 Turnstile 响应
                resp_ele = self.page.ele('css:input[name="cf-turnstile-response"]', timeout=1)
                if resp_ele:
                    val = resp_ele.attr("value")
                    if val and len(val) > 20:
                        logger.success("Turnstile 验证通过!")
                        break
                
                # 检查是否有错误
                if self.page.ele('text:Error verifying Turnstile', timeout=0.5):
                    logger.error("Turnstile 验证错误")
                    return False
                    
            except Exception as e:
                pass
            
            time.sleep(2)
            print(".", end="", flush=True)
        
        print("")
        
        if time.time() - start_time >= max_wait:
            logger.error("Turnstile 验证超时")
            return False
        
        # 点击确认按钮
        logger.info("查找确认按钮...")
        confirm_btn = self.page.ele('css:#renew-modal button[type="submit"]', timeout=5)
        if not confirm_btn:
            confirm_btn = self.page.ele('css:.modal button[type="submit"]', timeout=5)
        
        if confirm_btn:
            confirm_btn.click()
            logger.info("已点击确认按钮")
            time.sleep(5)
            
            # 检查结果
            html_lower = self.page.html.lower()
            if "success" in html_lower or "renewed" in html_lower:
                logger.success("🎉 续期成功!")
                return True
            else:
                logger.warning("未检测到明确的成功标识，但流程已完成")
                return True
        else:
            logger.error("找不到确认按钮")
            return False
    
    def run(self):
        """主运行流程"""
        logger.info("=" * 50)
        logger.info("KataBump 续期脚本启动")
        logger.info("=" * 50)
        
        # 验证环境变量
        if not KB_EMAIL or not KB_PASSWORD or not KB_RENEW_URL:
            logger.error("缺少必要的环境变量: KB_EMAIL, KB_PASSWORD, KB_RENEW_URL")
            send_telegram("续期失败: 缺少环境变量", success=False)
            return False
        
        logger.info(f"账号: {KB_EMAIL}")
        logger.info(f"续期 URL: {KB_RENEW_URL}")
        
        success = False
        
        try:
            # 步骤 1: API 登录
            if not self.login_via_api():
                logger.error("API 登录失败")
                send_telegram("续期失败: 登录失败", success=False)
                return False
            
            # 步骤 2: 检查服务器状态
            server_info = self.check_server_status()
            
            # 步骤 3: 浏览器续期
            success = self.renew_via_browser()
            
            if success:
                msg = f"服务器续期成功! 账号: {KB_EMAIL}"
                if server_info and server_info.get("name"):
                    msg += f", 服务器: {server_info['name']}"
                send_telegram(msg, success=True)
            else:
                send_telegram(f"续期失败! 账号: {KB_EMAIL}", success=False)
                
        except Exception as e:
            logger.error(f"运行异常: {e}")
            send_telegram(f"续期异常: {str(e)}", success=False)
            success = False
        finally:
            # 清理
            if self.browser:
                try:
                    self.browser.quit()
                except:
                    pass
        
        logger.info("=" * 50)
        logger.info(f"脚本执行完成，结果: {'成功' if success else '失败'}")
        logger.info("=" * 50)
        
        return success


if __name__ == "__main__":
    renewer = KataBumpRenewer()
    result = renewer.run()
    sys.exit(0 if result else 1)
