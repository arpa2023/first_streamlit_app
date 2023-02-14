import streamlit

streamlit.title("My parents new healthy dinner")

streamlit.header("🥣Breakfast Favorites")
streamlit.header('🍌🥭 Build Your Own Fruit Smoothie 🥝🍇')
streamlit.text("🥗 Omega 3 & Blueberry Oatmeal")
streamlit.text("🐔Kale, Spinach and Rocket Smoothie")
streamlit.text("🥑🍞Hard-Boiled-Free Range Egg")

import pandas
my_fruit_list = pandas.read.csv("https://uni-lab-files.s3.us-west-2.amazonaws.com/dabw/fruit_macros.txt)
streamlit.dataframe(my_fruit_list)
