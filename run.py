from application import create_app
from application.insert_csv import insert_csv_to_mysql


app = create_app()

if __name__ == '__main__':
    # insert_csv_to_mysql('Job Listings.csv')
    app.run(debug = True)
 