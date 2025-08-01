 @echo off
echo Testing Alpaca API Key...

REM Replace the values below with your actual keys
set ALPACA_KEY=PK2TCORGWSJ3W64KIT7G
set ALPACA_SECRET=v1HYfufQfmFxHT3IJBBz9nRvOtgyw5ISfylRz4dD
curl -X GET "https://paper-api.alpaca.markets/v2/account" ^
  -H "APCA-API-KEY-ID: %ALPACA_KEY%" ^
  -H "APCA-API-SECRET-KEY: %ALPACA_SECRET%"

pause