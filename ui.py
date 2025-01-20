import streamlit as st
import requests

# Set the layout to centered
st.set_page_config(layout="centered")

# Main Heading
st.title("SearchSage")
st.subheader("The future of Search Engines")
st.image('agent.jpg')
# Subheading

# Description text
st.write(
    """
    Welcome to SearchSage, a revolutionary way to search the web and gain insights.
    With our advanced technology, your queries are processed with precision to deliver the most relevant results.
    Simply enter your search query below and let SearchSage do the magic!
    """
)

# Input box for the search query
search_query = st.text_input(
    "Enter your search query:",
    placeholder="Type in to search the web"
)

# Search button
if st.button("Search"):
    # Check if the user entered a query
    if search_query.strip():
        try:
            # Send a GET request to the backend API (replace with your actual API URL)
            api_url = "http://127.0.0.1:8000/query"  # Update this URL
            params = {"message": search_query}
            print(params)
            response = requests.post(api_url, json={"message": search_query})

            # Handle the response
            if response.status_code == 200:
                result = response.json()
                # Assuming the API returns a 'result' key with the data
                st.markdown(f"### Result:\n{result.get('Final_result', 'No result found.')}")
            else:
                st.error(f"Error: Received status code {response.status_code}")
        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.warning("Please enter a search query before clicking 'Search'.")
