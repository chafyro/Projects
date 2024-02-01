import time
import math
from binance import Client
from collections import deque
from binance.enums import SIDE_BUY, SIDE_SELL

class TradingBot:
    def __init__(self, API_KEY: str, Secret_Key: str):
        self._client = Client(API_KEY, Secret_Key)

    def get_price(self, symbol: str) -> float:
        ticker = self._client.get_ticker(symbol=symbol)
        return float(ticker['lastPrice'])

class Asset:
    def __init__(self, bot: TradingBot, asset: str, price_history: int = 10):
        self._bot = bot
        self._asset = asset
        self._symbol = f'{self._asset}BTC'
        self._prices = deque(maxlen=price_history)

    def update(self):
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
    def __init__(self, bot: TradingBot, asset: Asset, max_asset_amount: float = 1000):
        self._bot = bot
        self._asset = asset
        self._symbol = asset._symbol
        self._order_id = None
        self._max_asset_amount = max_asset_amount

    def execute_strategy(self):
        try:
            current_price = self._asset.last_gain()
            target_profit = 0.001  # 0.1%

            # Check if there is an open order
            if self._order_id:
                order_status = self._bot._client.get_order(symbol=self._symbol, orderId=self._order_id)
                print(f"Order status: {order_status['status']}")
                if order_status['status'] == 'FILLED':
                    print(f"Order filled at price: {order_status['price']}")

                    # Calculate profit percentage
                    filled_price = float(order_status['price'])
                    profit_percentage = (current_price - filled_price) / filled_price

                    # If profit meets or exceeds the target, sell the same amount
                    if profit_percentage >= target_profit:
                        print(f"Target profit reached. Selling at price: {current_price}")
                        quantity_to_sell = float(order_status['executedQty'])
                        self.sell_with_retry(quantity_to_sell)
                    else:
                        print("Target profit not reached. Holding position.")

                    self._order_id = None

                elif order_status['status'] == 'NEW':
                    print("Order still open. Checking for target profit...")
                    self.check_target_profit(order_status)
                    return
                else:
                    print(f"Order status: {order_status['status']}")
                    return

            # No open order, determine whether to buy
            elif current_price > self._asset.moving_average(window_size=5):
                print("Buy Signal")
                btc_balance = float(self._bot._client.get_asset_balance(asset='BTC')['free'])
                print(f"BTC Balance: {btc_balance}")

                # Prompt the user for the amount of the specific asset to buy
                asset_to_buy = float(input(f"Enter the amount of {self._asset._asset} to buy: "))
                asset_to_buy = min(self._max_asset_amount, asset_to_buy)  # Ensure not to spend more than available balance

                # Calculate the BTC amount to spend
                btc_amount_to_spend = asset_to_buy * current_price

                # Check if current_price is non-zero before attempting division
                if current_price == 0:
                    print("Error: Current price is zero. Skipping buy order.")
                    return

                # Round the quantity to an appropriate number of decimal places
                precision = self._get_precision(self._symbol)
                btc_amount_to_spend = round(btc_amount_to_spend, precision)

                # Ensure that the total order value meets the NOTIONAL filter
                min_notional = self._get_min_notional(self._symbol)
                if btc_amount_to_spend < min_notional:
                    print(f"Total order value below the minimum notional: {btc_amount_to_spend} < {min_notional}")
                    return

                # Format the quantity to a string with up to 8 decimal places
                quantity = format(asset_to_buy / current_price, f'.{precision}f')

                if float(quantity) <= 0:
                    print(f"Calculated quantity is zero or negative. Skipping buy order.")
                    return


                order = self._bot._client.create_order(
                    symbol=self._symbol,
                    side=SIDE_BUY,
                    type='MARKET',
                    quantity=quantity
                )
                print(f"Buy order placed: {order}")
                self._order_id = order['orderId']

        except Exception as e:
            print(f"An error occurred: {e}")

    def sell_with_retry(self, quantity_to_sell):
        try_count = 0
        max_retries = 3

        while try_count < max_retries:
            try:
                order = self._bot._client.create_order(
                    symbol=self._symbol,
                    side=SIDE_SELL,
                    type='MARKET',
                    quantity=quantity_to_sell
                )
                print(f"Sell order placed: {order}")
                return
            except Exception as e:
                try_count += 1
                print(f"Error selling: {e}. Retrying ({try_count}/{max_retries})...")

        print(f"Failed to sell after {max_retries} attempts.")


    def check_target_profit(self, order_status):
        filled_price = float(order_status['price'])
        current_price = self._asset.last_gain()
        profit_percentage = (current_price - filled_price) / filled_price

        if profit_percentage >= 0.001:  # Adjust this threshold as needed
            print(f"Target profit reached. Closing order at price: {current_price}")
            self._bot._client.create_order(
                symbol=self._symbol,
                side=SIDE_SELL,
                type='MARKET',
                quantity=float(order_status['executedQty'])
            )
            self._order_id = None

    def _get_precision(self, symbol):
        exchange_info = self._bot._client.get_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == symbol:
                filters = symbol_info.get('filters', [])
                for filter_item in filters:
                    if filter_item['filterType'] == 'LOT_SIZE':
                        return int(-math.log10(float(filter_item['stepSize'])))
        raise RuntimeError(f"Symbol {symbol} not found in exchange info.")

    def _get_min_notional(self, symbol):
        exchange_info = self._bot._client.get_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == symbol:
                filters = symbol_info.get('filters', [])
                min_notional = float('inf')  # Initialize to a large value
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
                        if min_price is not None:
                            min_notional = min(min_notional, min_qty * step_size * min_price)

                return min_notional if min_notional != float('inf') else 0.001

        raise RuntimeError(f"Symbol {symbol} not found in exchange info.")

def main():
    API_KEY = 'mlCVFEXZaxWlnBhGP3xzGb3hFxVuLweifCKelQM77pQLS7ArgIxRJWxCOy3XIqC9'
    Secret_Key = 'FUbMlKn09q1tV8Ex3uU7wP8L0PKN4jMoEQWIk1Qqj4WRmrQgut5spk4rmMw3rEUu'

    bot = TradingBot(API_KEY, Secret_Key)

    # Prompt the user for the desired trading pair
    trading_pair = input("Enter the trading pair (e.g., ETH, LTC, etc.): ").upper()
    asset = Asset(bot, trading_pair)

    strategy = TradingStrategy(bot, asset)

    while True:
        try:
            # Update the price history
            asset.update()

            # Execute the trading strategy
            strategy.execute_strategy()

            # Sleep for a specified interval
            time.sleep(30)
        except KeyboardInterrupt:
            print("Exiting the trading bot.")
            break

if __name__ == "__main__":
    main()
