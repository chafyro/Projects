import time
from binance import Client
from collections import deque
from binance.enums import SIDE_BUY, SIDE_SELL

class TradingBot:
    def __init__(self, API_KEY: str, Secret_Key: str):
        self._client = Client(API_KEY, Secret_Key)

    def get_binance_client(self):
        return self._client

    def get_price(self, symbol: str) -> float:
        print(type(self._client))  # Debugging line
        tickers = self._client.get_all_tickers()
        for ticker in tickers:
            if ticker['symbol'] == symbol:
                return float(ticker['price'])
        raise RuntimeError(f'No symbol "{symbol}" was found')

class Asset:
    def __init__(self, bot: TradingBot, asset: str, price_history: int = 10):
        self._bot = bot
        self._asset = asset
        self._symbol = f'{asset}BTC'  
        self._prices = deque(maxlen=price_history)

    def update(self):
        current_price = self.get_price()  
        self._prices.append(current_price)

    def get_price(self) -> float:
        return self._bot.get_price(self._symbol)

    def last_gain(self) -> float:
        if len(self._prices) < 2:
            return 0
        return self._prices[-1] / self._prices[-2]

    def moving_average(self, window_size: int) -> float:
        if len(self._prices) < window_size:
            return 0
        return sum(self._prices) / window_size

class TradingStrategy:
    def __init__(self, bot: TradingBot, asset: Asset, max_btc_amount: float = 0.0001, target_profit: float = 0.001):
        self._bot = bot
        self._asset = asset
        self._symbol = asset._symbol
        self._order_id = None
        self._max_btc_amount = max_btc_amount
        self._target_profit = target_profit
        self._initial_quantity = None

    def execute_strategy(self):
        try:
            current_price = self._asset.last_gain()

            # Check if there is an open order
            if self._order_id:
                order_status = self._bot.get_binance_client().get_order(symbol=self._symbol, orderId=self._order_id)
                print(f"Order status: {order_status['status']}")
                if order_status['status'] == 'FILLED':
                    print(f"Order filled at price: {order_status['price']}")
                    self._order_id = None
                    self._initial_quantity = None  # Reset the initial quantity
                elif order_status['status'] == 'NEW':
                    print("Order still open. Checking for target profit...")
                    self.check_target_profit(order_status)
                    return
                else:
                    print(f"Order status: {order_status['status']}")
                    return

            # No open order, determine whether to buy or sell
            if current_price > self._asset.moving_average(window_size=5):
                print("Buy Signal")

                # If the initial quantity is not set, buy and set the initial quantity
                if self._initial_quantity is None:
                    self.buy()

            elif current_price < self._asset.moving_average(window_size=5):
                print("Sell Signal")

                # If the initial quantity is set, sell
                if self._initial_quantity is not None:
                    self.sell()

        except Exception as e:
            print(f"An error occurred: {e}")

    def buy(self):
        # Get the lot size precision for the trading pair
        precision = self._get_precision(self._symbol)

        # Round the quantity to match the lot size constraints
        quantity_to_buy = round(self._max_btc_amount / self._asset.get_price(self._symbol), precision)
        quantity_to_buy = self.adjust_to_lot_size(quantity_to_buy, precision)

        # Ensure that the total order value meets the NOTIONAL filter
        min_notional = self._get_min_notional(self._symbol)
        if quantity_to_buy * self._asset.get_price(self._symbol) < min_notional:
            print(f"Total order value below the minimum notional: {quantity_to_buy * self._asset.get_price(self._symbol)} < {min_notional}")
            return

        # Format the quantity to a string with up to 8 decimal places
        quantity = format(quantity_to_buy, f'.{precision}f')

        order = self._bot.get_binance_client().create_order(
            symbol=self._symbol,
            side=SIDE_BUY,
            type='MARKET',
            quantity=quantity
        )
        print(f"Buy order placed: {order}")
        self._order_id = order['orderId']
        self._initial_quantity = quantity_to_buy  # Set the initial quantity

    def sell(self):
        # Get the lot size precision for the trading pair
        precision = self._get_precision(self._symbol)

        # Round the quantity to match the lot size constraints
        quantity_to_sell = self._initial_quantity
        quantity_to_sell = self.adjust_to_lot_size(quantity_to_sell, precision)

        # Ensure that the total order value meets the NOTIONAL filter
        min_notional = self._get_min_notional(self._symbol)
        if quantity_to_sell * self._asset.get_price(self._symbol) < min_notional:
            print(f"Total order value below the minimum notional: {quantity_to_sell * self._asset.get_price(self._symbol)} < {min_notional}")
            return

        # Format the quantity to a string with up to 8 decimal places
        quantity = format(quantity_to_sell, f'.{precision}f')

        order = self._bot.get_binance_client().create_order(
            symbol=self._symbol,
            side=SIDE_SELL,
            type='MARKET',
            quantity=quantity
        )
        print(f"Sell order placed: {order}")
        self._order_id = None
        self._initial_quantity = None  # Reset the initial quantity

    def adjust_to_lot_size(self, quantity, precision):
        # Get the lot size step for the trading pair
        exchange_info = self._bot.get_binance_client().get_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == self._symbol:
                lot_size_filter = next(filter(lambda x: x['filterType'] == 'LOT_SIZE', symbol_info['filters']))
                step_size = float(lot_size_filter['stepSize'])
                return round(quantity / step_size) * step_size

        raise RuntimeError(f"Symbol {self._symbol} not found in exchange info.")

    def check_target_profit(self, order_status):
        filled_price = float(order_status['price'])
        current_price = self._asset.last_gain()
        profit_percentage = (current_price - filled_price) / filled_price

        if profit_percentage >= self._target_profit:
            print(f"Target profit reached ({self._target_profit * 100}%). Selling at price: {current_price}")
            self.sell()

    def _get_precision(self, symbol):
        exchange_info = self._bot.get_binance_client().get_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == symbol:
                return symbol_info['baseAssetPrecision']
        raise RuntimeError(f"Symbol {symbol} not found in exchange info.")

    def _get_min_notional(self, symbol):
        exchange_info = self._bot.get_binance_client().get_exchange_info()
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
                        if min_qty is not None and min_price is not None:
                            min_notional = min(min_notional, min_qty * step_size * min_price)

                return min_notional if min_notional != float('inf') else max(min_qty, 0.001)

        raise RuntimeError(f"Symbol {symbol} not found in exchange info.")

def main():
    API_KEY = 'mlCVFEXZaxWlnBhGP3xzGb3hFxVuLweifCKelQM77pQLS7ArgIxRJWxCOy3XIqC9'
    Secret_Key = 'FUbMlKn09q1tV8Ex3uU7wP8L0PKN4jMoEQWIk1Qqj4WRmrQgut5spk4rmMw3rEUu'

    client = Client(API_KEY, Secret_Key)
    bot = TradingBot(API_KEY, Secret_Key)

    # Prompt the user for the desired trading pair
    trading_pair = input("Enter the trading pair (e.g., ETH, LTC, etc.): ").upper()
    asset = Asset(bot, trading_pair)

    strategy = TradingStrategy(bot, asset, max_btc_amount=0.0001)

    while True:
        # Update the price history
        asset.update()

        # Execute the trading strategy
        strategy.execute_strategy()

        # Sleep for a specified interval
        time.sleep(30)

if __name__ == "__main__":
    main()
