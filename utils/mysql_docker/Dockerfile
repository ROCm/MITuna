FROM mysql:8.0

ARG MYSQL_PWD
ARG MYSQL_DB
ENV MYSQL_ROOT_PASSWORD={MYSQL_PWD}
ENV MYSQL_DATABASE={MYSQL_DB}


ARG DB_NAME
ARG DB_USER_NAME
ARG DB_USER_PASSWORD

ENV TUNA_DB_NAME={DB_NAME}
ENV TUNA_DB_USER_NAME={DB_USER_NAME}
ENV TUNA_DB_USER_PASSWORD={DB_USER_PASSWORD}
ENV TUNA_DB_HOSTNAME=localhost

WORKDIR /root/
ADD requirements.txt requirements.txt
RUN apt update 
RUN apt install -y python3 python3-pip vim
RUN pip3 install -r requirements.txt
ADD ./bin/schema.sql /docker-entrypoint-initdb.d/0_schema.sql
ADD ./bin/recurrent_data.sql /docker-entrypoint-initdb.d/1_recurrent_data.sql

