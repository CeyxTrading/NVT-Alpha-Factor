# NVT-Alpha-Factor
Network-Value-To-Transaction Alpha Factor for Crypto Trading
Requirements:
numpy
pandas
PyWavelets
yfinance
matplotlib

The Network Value-to-Transaction ratio (NVT) measures the daily transaction value per market capitalization, and is calculated by dividing the daily market cap by the daily transaction volume

A high NVT suggests that the cryptocurrency's valuation is higher than the value it's transmitting, which might indicate overvaluation. On the other hand, a low NVT can suggest that the cryptocurrency is undervalued compared to the utility it provides in terms of transaction volume

It involves calculating the NVT for each coin and day, dividing the coins into percent quantiles based on the NVT, and allocating investments based on five buckets. The top bucket with the highest NVT gets the most allocation, and so on. The portfolio is rebalanced daily

Data Aquisition you can use Coingecko or CryptoCompare API
