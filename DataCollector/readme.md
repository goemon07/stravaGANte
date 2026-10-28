# Data collection phase


## Crowdsourced Strava data collection

Follow the indication in the [official documentation](https://developers.strava.com/docs/getting-started/). You need your own Strava API application; replace `<YOUR_CLIENT_ID>` below with its client ID.

1. Let them accept from this link:
www.strava.com/oauth/authorize?client_id=<YOUR_CLIENT_ID>&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=read

The link for API documentation is [here](https://developers.strava.com/docs/reference/#api-Athletes-getLoggedInAthlete).