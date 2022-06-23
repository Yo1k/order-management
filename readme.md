# Order-management

<p align="right">
  <a href="https://docs.python.org/3.9/">
    <img src="https://img.shields.io/badge/Python-3.9-FFE873.svg?labelColor=4B8BBE"
        alt="Python requirement">
  </a>
</p>

## About

A data flow service (hereinafter referred to as 'data_flow'):
* gets data from Google Sheets using Google API;
* adds this data in its origin form to own database with an additional column 'cost in rubles';
  * gets US dollar quotes for converting $ into rubles from
  [CBR](https://www.cbr.ru/development/SXML/);
* uses telegram bot to send notification messages about missed deadlines orders.

Tech stack: \
[Google API Client Library](https://googleapis.github.io/google-api-python-client/docs/),
[PostgreSQL](https://www.postgresql.org/),
[psycopg3](https://www.psycopg.org/psycopg3/docs/),
[python-telegram-bot 13.12](https://docs.python-telegram-bot.org/en/v13.12/),
[Docker](https://www.docker.com/)

## Сomments for the reviewer

Here are the links to
[orders_info](https://docs.google.com/spreadsheets/d/1uqzyZbTDQWjVCbGiFlr2pS8GbUQpyW-3bJ3WqCwMz7E/edit?usp=sharing) (Google Sheets file),
[developer_key](https://drive.google.com/file/d/1wbm6PWYKQp2BcLH_HbHQgNrMNoM-Nr5j/view?usp=sharing) (API key, credential to access 'orders_info' from the 'data_flow' service),
and [telegram_api_token](https://drive.google.com/file/d/1N_BGZZuqXvFFdaJTEaOq1LPSIUDWDUq7/view?usp=sharing). 'orders_info' can be viewed by anyone who has the link. User sales@numbersss.com has 
permission to edit `orders_info` and view `developer_key`, `telegram_api_token` on Google Drive.

To receive notifications from the telegram bot follow the [link](http://t.me/Yo1k_order_management_bot) 
or directly add bot with the name '@Yo1k_order_management_bot'.

## Docker instructions

Clone this git repository.
Replace empty `developer_key` file by a file [from here](https://drive.google.com/file/d/1wbm6PWYKQp2BcLH_HbHQgNrMNoM-Nr5j/view?usp=sharing)
and `telegram_api_token` file by a file [from here](https://drive.google.com/file/d/1N_BGZZuqXvFFdaJTEaOq1LPSIUDWDUq7/view?usp=sharing). \
Before starting, [install Docker Compose](https://docs.docker.com/compose/install/) if you do not have 
it. Below it is assumed that
[Docker's repositories](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository)
are set up. By default, the Docker daemon always runs as the `root` user. If you do not want to 
preface the docker command with `sudo` see
[this](https://docs.docker.com/engine/install/linux-postinstall/). Start Docker daemon with command:

```shell
$ sudo service docker start
```

### Build image

`Dockerfile` describes modifications of [Python 3.9 parent image](https://hub.docker.com/r/library/python/tags/3.9)
needed to build 'data_flow' image. \
To build Docker's 'data_flow' image, run the following from the project 
root directory: 

```shell
$ sudo docker build --tag data_flow .
```

### Run containers

`docker-compose.yml` describes two services: 'db' ans 'web'. 'db' is 
service with PostgreSQL DBMS. 
The 'postgres' image is used to start 'db'. 'db' uses volumes at path `./data/db` for 
containing DB data.  See the 
[reference](https://docs.docker.com/compose/compose-file/) for more 
information about structure `docker-compose.yml`.
'web' is service that runs 'data_flow' image and also has dependency on 'db'. Make sure you create 
the 'data_flow' image before starting the services.

To create and run Docker container with 'data_flow' application, run from the project root 
directory (be sure that postgres DBMS do not running):

```shell
$ sudo docker compose up
```

or use flag `-d` to start the service in the background

```shell
$ sudo docker compose up -d
```

To shut down running services and clean up containers, use either of these methods:
* stop the application by typing `Ctrl-C` in the same shell (if the service is running in the 
  foreground) 
  in where you started it, then use `sudo docker rm <CONTAINER ID | NAME>` to remove containers 
  (to see containers list `sudo docker ps -a`)
* or switch to a different shell and run from the project root directory

```shell
$ sudo docker compose down
```

## PostgreSQL

To connect to running 'db' service with PostgreSQL, run:

```shell
$ psql -U postgres -W -h 127.0.0.1 -p 5432 postgres
```

Input password: 'postgres'. It is assumed you have psql - PostgreSQL interactive terminal.
