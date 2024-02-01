import time
import math
from binance import Client
from collections import deque
from binance.enums import SIDE_BUY, SIDE_SELL

class TradingBot:
    def __init__(self, API_KEY: str, Secret_Key: str):
        self._client = Client(API_KEY, Secret_Key)

    def get_price(self, symbol: str) -> float:
        ticker = self._client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])

class Asset:
    def __init__(self, bot: TradingBot, asset: str, base_asset: str = 'BTC', price_history: int = 10):
        self._bot = bot
        self._asset = asset.upper()  
        self._base_asset = base_asset.upper()  
        self._prices = deque(maxlen=price_history)
        self._symbol = None  

    @property
    def symbol(self):
        if self._symbol is None:
            raise ValueError("Symbol not yet initialized. Call update() first.")
        return self._symbol

    def update_symbol(self):
        exchange_info = self._bot._client.get_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['baseAsset'] == self._asset and symbol_info['quoteAsset'] == self._base_asset:
                self._symbol = symbol_info['symbol']
                break
        else:
            # If the direct pair is not found, try finding the reverse pair
            for symbol_info in exchange_info['symbols']:
                if symbol_info['baseAsset'] == self._base_asset and symbol_info['quoteAsset'] == self._asset:
                    self._symbol = symbol_info['symbol']
                    break

        if self._symbol is None:
            raise ValueError(f"Symbol not found for {self._asset}{self._base_asset}")
    def update(self):
        self.update_symbol()
        self._prices.append(self._bot.get_price(self._symbol))
        
    def last_gain(self) -> float:
        if len(self._prices) < 2:
            return 0
        return self._prices[-1] / self._prices[-2]
    
    def moving_average(self, window_size: int) -> float:
        if len(self._prices) < window_size:
            return 0
        return sum(self._prices) / window_size

class TradingStrategy:
    def __init__(self, bot: TradingBot, asset: Asset, target_profit: float = 0.01):
        self._bot = bot
        self._asset = asset
        self._symbol = asset.symbol
        self._order_id = None
        self._target_profit = target_profit

    def execute_strategy(self):
        try:
            current_price = self._asset.last_gain()
            print(f"Current Price: {current_price}")

            # Check if there is an open order
            if self._order_id:
                order_status = self._bot._client.get_order(symbol=self._symbol, orderId=self._order_id)
                print(f"Order status: {order_status['status']}")
                if order_status['status'] == 'FILLED':
                    print(f"Order filled at price: {order_status['price']}")
                    self._order_id = None
                elif order_status['status'] == 'NEW':
                    print("Order still open. Checking for target profit...")
                    self.check_target_profit(order_status, current_price)
                    return
                else:
                    print(f"Order status: {order_status['status']}")
                    return
                
            # No open order, determine whether to buy or sell
            if current_price > self._asset.moving_average(window_size=5):
                print("Buy Signal")
                btc_balance = self._bot._client.get_asset_balance(asset='BTC')['free']
                print(f"BTC Balance: {btc_balance}")

                # Calculate the quantity of the desired coin to buy
                quantity_precision = self._get_precision(self._symbol, 'quantity')
                coin_quantity = round(float(btc_balance) / current_price, quantity_precision)

                # Get the step size from the LOT_SIZE filter
                step_size = self._get_lot_size_step_size(self._symbol)

                # Ensure that the quantity conforms to the LOT_SIZE filter
                coin_quantity = round(coin_quantity / step_size) * step_size

                # Ensure that the total order value meets the NOTIONAL filter
                min_notional = self._get_min_notional(self._symbol, current_price)
                if coin_quantity * current_price < min_notional:
                    print(f"Total order value below the minimum notional: {coin_quantity * current_price} < {min_notional}")
                    return

                order = self._bot._client.create_order(
                    symbol=self._symbol,
                    side=SIDE_BUY,
                    type='MARKET',
                    quantity=coin_quantity
                )

                print(f"Buy order placed: {order}")
                self._order_id = order['orderId']

            elif current_price < self._asset.moving_average(window_size=5):
                print("Sell Signal")
                asset_balance = self._bot._client.get_asset_balance(asset=self._asset._asset)['free']
                print(f"Asset Balance: {asset_balance}")

                # Calculate the quantity of the desired coin to sell
                quantity_precision = self._get_precision(self._symbol, 'quantity')
                coin_quantity = min(float(asset_balance), 1000)  # Replace with your desired asset amount
                coin_quantity = round(coin_quantity, quantity_precision)

                # Ensure that the total order value meets the NOTIONAL filter
                total_order_value = coin_quantity * current_price
                min_notional = self._get_min_notional(self._symbol, current_price)
                print(f"Total Order Value: {total_order_value}, Min Notional: {min_notional}")

                if total_order_value < min_notional:
                    print(f"Total order value below the minimum notional: {total_order_value} < {min_notional}")
                    return

                # Format the quantity to a string with up to 8 decimal places
                formatted_quantity = format(coin_quantity, f'.{quantity_precision}f')

                order = self._bot._client.create_order(
                    symbol=self._symbol,
                    side=SIDE_SELL,
                    type='MARKET',
                    quantity=formatted_quantity
                )

                print(f"Sell order placed: {order}")
                self._order_id = order['orderId']

        except Exception as e:
            print(f"An error occurred: {e}")

    def check_target_profit(self, order_status, current_price):
        filled_price = float(order_status['price'])
        profit_percentage = (current_price - filled_price) / filled_price

        if profit_percentage >= self._target_profit:
            print(f"Target profit reached ({self._target_profit * 100}%). Closing order at price: {current_price}")
            self._bot._client.create_order(
                symbol=self._symbol,
                side=SIDE_SELL,
                type='MARKET',
                quantity=float(order_status['executedQty'])
            )
            self._order_id = None

    def _get_precision(self, symbol, precision_type):
        exchange_info = self._bot._client.get_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == symbol:
                filters = symbol_info.get('filters', [])
                for filter_item in filters:
                    if filter_item['filterType'] == precision_type:
                        return int(-math.log10(float(filter_item['stepSize'])))
        raise RuntimeError(f"Symbol {symbol} not found in exchange info.")
    
    def _get_min_notional(self, symbol, current_price):
        exchange_info = self._bot._client.get_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == symbol:
                filters = symbol_info.get('filters', [])
                min_notional = float('inf')  # Initialize to a large value
                min_qty = None
                min_price = None
                for filter_item in filters:
                    if filter_item['filterType'] == 'MIN_NOTIONAL':
                        min_notional = float(filter_item['minNotional'])
                    elif filter_item['filterType'] == 'PRICE_FILTER':
                        min_price = float(filter_item['minPrice'])
                        tick_size = float(filter_item['tickSize'])
                        if min_price is not None:
                            min_notional = min(min_notional, min_price * tick_size)
                    elif filter_item['filterType'] == 'LOT_SIZE':
                        min_qty = float(filter_item['minQty'])
                        step_size = float(filter_item['stepSize'])
                        if min_qty is not None and current_price is not None:
                            min_notional = min(min_notional, min_qty * current_price)

                return min_notional if min_notional != float('inf') else max(min_qty, 0.001)

        raise RuntimeError(f"Symbol {symbol} not found in exchange info.")

def main():
    API_KEY = 'mlCVFEXZaxWlnBhGP3xzGb3hFxVuLweifCKelQM77pQLS7ArgIxRJWxCOy3XIqC9'
    Secret_Key = 'FUbMlKn09q1tV8Ex3uU7wP8L0PKN4jMoEQWIk1Qqj4WRmrQgut5spk4rmMw3rEUu'

    client = Client(API_KEY, Secret_Key)
    bot = TradingBot(API_KEY, Secret_Key)

    while True:
        # Prompt the user for the desired trading pair
        trading_pair = input("Enter the trading pair (e.g., ETH, LTC, etc.): ").upper()
        asset = Asset(bot, trading_pair)

        # Update the price history and symbol
        asset.update()

        # Create TradingStrategy instance after updating the symbol
        strategy = TradingStrategy(bot, asset)

        # Execute the trading strategy
        strategy.execute_strategy()

        # Sleep for a specified interval
        time.sleep(30)

if __name__ == "__main__":
    main()
