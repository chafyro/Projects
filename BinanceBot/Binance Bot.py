#Binance Bot
#Symbol = XRP/BTC
#Buy
# 1XRP = 0,000018BTC
#Sell
#1BTC = 1/0,000018XRP = 55.555,5556XRP

import time
from binance import Client
from collections import deque

import pandas as pd 

API_KEY = 'mlCVFEXZaxWlnBhGP3xzGb3hFxVuLweifCKelQM77pQLS7ArgIxRJWxCOy3XIqC9'
Secret_Key = 'FUbMlKn09q1tV8Ex3uU7wP8L0PKN4jMoEQWIk1Qqj4WRmrQgut5spk4rmMw3rEUu'

class TradingBot:
    def __init__(self, API_KEY: str, Secret_Key: str):
        self._client = Client(API_KEY, Secret_Key)
    
    def get_price(self, symbol: str) -> float:
        tickers = self._client.get_all_tickers()
        for ticker in tickers : 
            if ticker ['symbol'] == symbol:
                return float(ticker['price'])
        raise RuntimeError(f'No symbol “{symbol}“ was found')

class Asset:
    def __init__(self, bot: TradingBot, asset: str, price_history: int = 10):
        self._bot = bot
        self._asset = asset
        self._symbol = f'{self._asset}BTC'
        self._prices = deque(maxlen=price_history ) 
        
    def update(self):
        self._prices.append(self._bot.get_price(self._symbol))
        #first price is the old last price is the new 
    
    def last_gain(self) -> float:
        if len(self._prices) <2:
            return 0
        return self._prices[-1] / self._prices[-2]

def main ():
    client = Client(API_KEY, Secret_Key)
   
    
    bot = TradingBot(API_KEY, Secret_Key)
    asset = Asset(bot, 'XRP')
    
    try:
        while True:
            asset.update()
            print(asset.last_gain())
            time.sleep(30)
    except KeyboardInterrupt:
        print('Done')   
if __name__ == '__main__':
    main()