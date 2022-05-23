# homework_bot
This project is a Telegram bot that accesses the API of the Praktikum service. The bot will know if the homework was taken in the review, whether it has been checked, failed or accepted, and sends the result (homework status) to your Telegram chat.
The bot regularly polls the homework API and, upon receiving updates, parses the response and sends a message to the Telegram account. 
FileHandler and StreamHandler handlers are used for logs. ERROR events are sent to the Telegram account.
