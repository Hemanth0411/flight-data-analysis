import os
from amadeus import Client, ResponseError
import pandas as pd
import google.generativeai as genai
from flask import Flask, render_template, request
from dotenv import load_dotenv
import plotly.express as px
import markdown

# Load secret API keys from the .env file
load_dotenv()

# Create the Flask web app
app = Flask(__name__)


# Creates a price comparison bar chart using Plotly
def create_price_chart(df):
    if df is None or df.empty:
        return None
    
    lowest_prices_df = df.groupby('airline')['price'].min().reset_index()
    
    fig = px.bar(
        lowest_prices_df,
        x='airline',
        y='price',
        title='Lowest Price by Airline',
        labels={'airline': 'Airline Code', 'price': 'Price (AUD)'},
        text='price'
    )
    fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    return fig.to_html(full_html=False)


# Main page of the web app
@app.route('/', methods=['GET', 'POST'])
def index():
    insights_html = None 
    chart_div = None

    # This block runs when the user submits the form
    if request.method == 'POST':
        origin = request.form['origin']
        destination = request.form['destination']
        date = request.form['date']

        flight_data_df = fetch_flight_offers(origin, destination, date)

        if flight_data_df is not None and not flight_data_df.empty:
            raw_insights_text = get_demand_insights(flight_data_df)
            insights_html = markdown.markdown(raw_insights_text)
            chart_div = create_price_chart(flight_data_df)
        else:
            insights_html = f"<p>Sorry, no flight offers were found for {origin} to {destination} on {date}.</p>"

    return render_template('index.html', insights=insights_html, chart_div=chart_div)


# Asks the Gemini AI to analyze the data and provide a summary
def get_demand_insights(df):
    if df is None or df.empty:
        return "No flight data available to analyze."

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt = f"""
    As a travel market analyst for a group of Australian hostels, analyze the following airline booking data and provide a short summary of market demand.
    The data is for flights on a specific route.

    Data (in CSV format):
    {df.to_csv()}

    Your analysis should be a brief paragraph covering these key points:
    1.  **Pricing:** What is the average price? Is there a wide range of prices?
    2.  **Popular Carriers:** Which airlines are operating most on this route?
    3.  **Demand Signal:** Based on the prices and number of offers, does demand seem high, low, or moderate?

    Provide a concise, easy-to-read summary for a non-technical manager.
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "Could not generate insights due to an error."


# Fetches flight data from the Amadeus API
def fetch_flight_offers(origin, destination, date):
    try:
        amadeus = Client(
            client_id=os.getenv("AMADEUS_CLIENT_ID"),
            client_secret=os.getenv("AMADEUS_CLIENT_SECRET")
        )
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode=origin,
            destinationLocationCode=destination,
            departureDate=date,
            adults=1,
            currencyCode='AUD',
            max=15
        )

        flights_df = pd.DataFrame([
            {
                "airline": offer['itineraries'][0]['segments'][0]['carrierCode'],
                "price": float(offer['price']['total']),
                "stops": len(offer['itineraries'][0]['segments']) - 1
            } for offer in response.data
        ])
        return flights_df
    except ResponseError as error:
        print(f"Amadeus API Error: {error}")
        return None