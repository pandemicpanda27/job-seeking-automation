from application import create_app

app = create_app()

if __name__ == '__main__':
    print("\n" + "="*60)
    print(" Job Seeking Automation - Starting...")
    print("="*60)
    print(" Access at: http://localhost:5000")
    print(" Press CTRL+C to stop")
    print("="*60 + "\n")
    app.run(debug=True)
