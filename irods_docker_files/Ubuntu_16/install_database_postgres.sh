#! /bin/bash

if [ "$DATABASE" = "postgres" ]; then
    apt-get update
    apt-get -y install postgresql postgresql-contrib odbc-postgresql unixodbc super
    service postgresql start

    if [ -e /tmp/db_commands.txt ]
    then 
        su - postgres -c 'psql -f /tmp/db_commands.txt'
    else
        echo "nok"
    fi
    
else
    echo $DATABASE
fi
