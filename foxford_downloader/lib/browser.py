from pyppeteer import connect, launch
import psutil
import signal
import os


class BrowserConnectionManager:
    def __init__(self):
        self.connection = None

    async def get_connection_url(self) -> str:
        if self.connection is None:
            browser = await launch(
                ignoreHTTPSErrors=True,
                headless=True,
                slowMo=0,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    '--proxy-server="direct://"',
                    "--proxy-bypass-list=*"
                ]
            )

            connection_url = browser.wsEndpoint
            await browser.disconnect()
            self.connection = connection_url
            return connection_url
        else:
            return self.connection

    async def terminate_connection(self, browser=None):
        print(0)
        if self.connection is not None:
            print(1)
            browser_endpoint = self.connection
            if browser is None:
                browser = await connect(browserWSEndpoint=browser_endpoint)
            print(2)

            try:
                parent = psutil.Process(os.getpid())
            except psutil.NoSuchProcess:
                return
            children = parent.children(recursive=True)
            print(children)
            for process in children:
                process.send_signal(signal.SIGTERM)

            #await browser.close()
            print(3)
            self.connection = None
