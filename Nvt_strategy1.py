import requests
import pandas as pd
import os
import datetime
import json
import time
import plotly.graph_objects as go


# todo
crypto_compare_api_key = "<Your API key>"

#  Output directories
CACHE_DIR = "cache"
RESULTS_DIR = "results"


def lookup_coin_id(symbol):
    try:

        # Check for cached data
        cache_file_name = f"{symbol}_coin_id.csv"
        cache_file_path = os.path.join(CACHE_DIR, cache_file_name)

        if os.path.exists(cache_file_path):
            coin_id_df = pd.read_csv(cache_file_path)
            return coin_id_df.iloc[0]['coin_id']
        else:
            url = f"https://api.coingecko.com/api/v3/search?query={symbol}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept': 'application/json'
            }

            #  Send GET request
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                response_json = json.loads(response.text)
                coins = response_json['coins']
                if len(coins) > 0:
                    #  Get the first result
                    first_result = coins[0]
                    coin_id = first_result["id"]

                    # Save the coin_id to cache
                    coin_id_df = pd.DataFrame([{"coin_id": coin_id}])
                    coin_id_df.to_csv(cache_file_path, index=False)

                    return coin_id
            return None
    except Exception as ex:
        print(f"Failed to to look up coin id: {ex}")


def fetch_prices(coin_id, start_date_epoch, end_date_epoch):
    try:
        file_name = f"{coin_id}_{start_date_epoch}_{end_date_epoch}_prices.csv"
        path = os.path.join(CACHE_DIR, file_name)
        if os.path.exists(path):
            prices_df = pd.read_csv(path)
            prices_df['date'] = pd.to_datetime(prices_df['date'])
            return prices_df
        else:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
            params = {
                'vs_currency': 'usd',
                'from': start_date_epoch,
                'to': end_date_epoch,
                'precision': 6
            }

            response = requests.get(url, params=params)
            data = response.json()

            # Create individual DataFrames for prices, market caps, and volumes
            prices_df = pd.DataFrame(data['prices'], columns=['date', 'price'])
            market_caps_df = pd.DataFrame(data['market_caps'], columns=['date', 'market_cap'])
            total_volumes_df = pd.DataFrame(data['total_volumes'], columns=['date', 'volume'])

            # Convert epoch dates to datetime format for each DataFrame
            prices_df['date'] = pd.to_datetime(prices_df['date'], unit='ms')
            market_caps_df['date'] = pd.to_datetime(market_caps_df['date'], unit='ms')
            total_volumes_df['date'] = pd.to_datetime(total_volumes_df['date'], unit='ms')

            # Merge the DataFrames on the date column
            merged_df = prices_df.merge(market_caps_df, on='date', how='outer')
            merged_df = merged_df.merge(total_volumes_df, on='date', how='outer')

            # Sort by date
            merged_df = merged_df.sort_values(by='date')

            #  Store data
            merged_df.to_csv(path)

            return merged_df
    except Exception as ex:
        print(f"Failed to execute Coingecko call: {ex}")


def fetch_transactions(symbol, start_timestamp):
    try:
        file_name = f"{symbol}_{start_timestamp}_transactions.csv"
        path = os.path.join(CACHE_DIR, file_name)
        if os.path.exists(path):
            transactions_df = pd.read_csv(path)
            transactions_df['date'] = pd.to_datetime(transactions_df['date'])
            return transactions_df
        else:
            url = f"https://min-api.cryptocompare.com/data/blockchain/histo/day?fsym={symbol}&limit=2000&toTs={start_timestamp}&apiKey={crypto_compare_api_key}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept': 'application/json'
            }
            #  Send GET request
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                response_json = json.loads(response.text)
                if 'Response' in response_json and response_json['Response'] == 'Error':
                    return None

                data_list = response_json['Data']['Data']
                data_array = []
                for entry in data_list:
                    data_row = {
                        "time": entry["time"],
                        "transaction_count": entry["transaction_count"],
                        "current_supply": entry["current_supply"],
                        "new_addresses": entry["new_addresses"],
                        "active_addresses": entry["active_addresses"],
                    }
                    data_array.append(data_row)

                # Convert data_array to DataFrame
                transactions_df = pd.DataFrame(data_array)

                #  Convert epoch date
                transactions_df['date'] = pd.to_datetime(transactions_df['time'], unit='s')
                if transactions_df['date'].dtype == 'datetime64[ns, UTC]':
                    transactions_df['date'] = transactions_df['date'].dt.tz_localize(None)

                transactions_df.to_csv(path, index=False)  # Save the dataframe to csv for future use
                return transactions_df
    except Exception as ex:
        print(f"Failed to fetch transaction count: {ex}")


def execute_nvt_strategy(data_df):
    initial_balance = 10000
    daily_balance = [initial_balance]
    coins_held = {}

    date_list = data_df['date'].unique()
    for date in date_list:
        # Filter data for the given date
        daily_data_df = data_df[data_df['date'] == date]

        #  Get portfolio value of yesterday's coins
        daily_value = 0
        if date == data_df['date'].iloc[0]:  # If it's the first date in the dataset
            daily_value = initial_balance

        for symbol, quantity in coins_held.items():
            # Get the price of the crypto for the current day
            crypto_data_df = daily_data_df[daily_data_df['symbol'] == symbol]
            if not crypto_data_df.empty:
                price = crypto_data_df.iloc[0]['price']
                daily_value += price * quantity

        # Add the value to the daily balance list
        daily_balance.append(daily_value)

        # Sort the data for the current day by NVT in descending order and pick the top x coins
        num_top_coins = 4
        top_df = daily_data_df.sort_values(by='NVT', ascending=False).head(num_top_coins)

        # Calculate the amount to invest in each crypto
        amount_per_crypto = daily_balance[-1] / num_top_coins

        # Reset portfolio
        coins_held = {}

        #  Buy coins for today
        for index, row in top_df.iterrows():
            symbol = row['symbol']
            price = row['price']
            quantity_bought = amount_per_crypto / price

            # Update the coins bought today
            coins_held[symbol] = quantity_bought

    # Calculate the total return
    absolute_return = daily_balance[-1] - initial_balance
    relative_return = absolute_return / initial_balance

    return daily_balance, relative_return


def plot_daily_balance(daily_balance):
    fig = go.Figure(data=[go.Scatter(
        x=list(range(len(daily_balance))),
        y=daily_balance,
        mode='lines',
        name='Daily Balance'
    )])

    # Set the layout for the plot
    fig.update_layout(
        title="Daily Balance Over Time",
        xaxis_title="Days",
        yaxis_title="Balance in USD",
        font=dict(
            family="Courier New, monospace",
            size=18,
            color="#7f7f7f"
        )
    )

    file_name = "crypto_nvt_daily_balance.png"
    path = os.path.join(RESULTS_DIR, file_name)
    fig.write_image(path, format="png")

    # Show the plot
    fig.show()


def remove_outliers_iqr(df, column_name):
    Q1_price_change = df[column_name].quantile(0.25)
    Q3_price_change = df[column_name].quantile(0.75)
    IQR_price_change = Q3_price_change - Q1_price_change
    iqr_filter = (
        (df[column_name] >= Q1_price_change - 1.5 * IQR_price_change) &
        (df[column_name] <= Q3_price_change + 1.5 * IQR_price_change)
    )
    df = df[iqr_filter]
    return df


def plot_percentage_change_nvt(data_df):
    data_df['PricePercentChange'] = data_df['price'].pct_change(1)
    symbols = data_df['symbol'].unique()

    # Remove outliers based on IQR
    data_df = remove_outliers_iqr(data_df, 'PricePercentChange')
    data_df = remove_outliers_iqr(data_df, 'NVT')

    fig = go.Figure()

    for asset in symbols:
        asset_data_df = data_df[data_df['symbol'] == asset]
        fig.add_trace(go.Scatter(x=asset_data_df['NVT'],
                                 y=asset_data_df['PricePercentChange'],
                                 mode='markers',
                                 name=asset,
                                 text=asset_data_df['date'],
                                 hoverinfo='text+name+x+y'))

    fig.update_layout(
        title="Price Change vs. NVT Value Plot",
        xaxis_title="NVT Value",
        yaxis_title="Price Change",
        hovermode="closest"
    )

    file_name = "crypto_nvt_price_change_nvt.png"
    path = os.path.join(RESULTS_DIR, file_name)
    fig.write_image(path, format="png")

    fig.show()


if __name__ == '__main__':
    #  Create output directories
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)

    #  Define list of coins
    symbols = ['ADA', 'BCH', 'BTC', 'DASH', 'DOGE', 'ETC', 'ETH', 'HT', 'KCS', 'LTC', 'LINK', 'MANA', 'MKR', 'NEXO', 'SNX', 'THETA', 'USDT', 'VET', 'ZEC', 'ZIL']

    #  Set start and end dates:
    end_date_str = "2018-10-01"
    end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
    start_date = end_date - datetime.timedelta(days=2000)

    # Convert to epoch format
    start_date_epoch = int(start_date.timestamp())
    end_date_epoch = int(end_date.timestamp())

    # Iterate through symbols
    all_merged_df = pd.DataFrame()
    for symbol in symbols:
        print(f"Processing {symbol}...")

        #  Throttle CoinGecko requests
        time.sleep(6)

        #  Look up CoinGecko coin id
        coin_id = lookup_coin_id(symbol)
        if coin_id is None:
            print(f"No coin_id for {symbol}")
            continue

        #  Throttle CoinGecko requests
        time.sleep(6)

        #  Fetch historic prices
        prices_df = fetch_prices(coin_id, start_date_epoch, end_date_epoch)
        if prices_df is None or len(prices_df) == 0:
            print(f"No prices for {symbol}")
            continue

        #  Fetch historic transactions
        transactions_df = fetch_transactions(symbol, end_date_epoch)
        if transactions_df is None or len(transactions_df) == 0:
            print(f"No transactions for {symbol}")
            continue

        #  Merge on date
        merged_df = pd.merge(prices_df, transactions_df, left_on='date', right_on='date', how='inner')
        merged_df['symbol'] = symbol

        #  Calculate NVT
        merged_df['NVT'] = merged_df['market_cap'] / merged_df['transaction_count']

        #  Add to all results
        all_merged_df = pd.concat([all_merged_df, merged_df], axis=0, ignore_index=True)

    # Store all results
    path = os.path.join(RESULTS_DIR, 'all_merged_df.csv')
    all_merged_df.to_csv(path)

    #  Execute the strategy
    daily_balance, relative_return = execute_nvt_strategy(all_merged_df)
    print(f"Total Return: {relative_return * 100:.2f}%")

    # Plot the daily balance
    plot_daily_balance(daily_balance)

    #  Plot Percentage Change versus NVT
    plot_percentage_change_nvt(all_merged_df)
