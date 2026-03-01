from litellm.proxy.proxy_server import app
from mangum import Mangum

handler = Mangum(app, lifespan="on")
