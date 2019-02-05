#! /bin/bash

test_name=$3

if [ "$1" = 'Ubuntu_16' ]; then
    if [ -d /irods_build/Ubuntu_16 ]; then
        cd /irods_build/Ubuntu_16
        dpkg -i irods-runtime*.deb irods-dev*.deb irods-server*.deb irods-icommands*.deb
        if [ "$2" = 'postgres' ]; then
            dpkg -i irods-database-plugin-postgres*.deb

            # Start the Postgres database.
            service postgresql start
            until pg_isready -q
            do
               echo waiting for database ...
               sleep 1
            done

            # Set up iRODS.
            python /var/lib/irods/scripts/setup_irods.py < /var/lib/irods/packaging/localhost_setup_postgres.input
        fi
    fi
else 
    echo $test_name
fi

# Run test.
tests=/var/lib/irods/test/test_output.txt
su - irods -c "cd scripts; python run_tests.py --xml_output --run_specific_test $test_name > $tests 2>&1"
ec=$?

# Make test results available to docker host.
[ ! -d /irods_test_env/$test_name ] && mkdir /irods_test_env/$test_name
cd /var/lib/irods
#cp log/rodsLog* log/rodsServerLog* log/test_log.txt test/test_output.txt /irods_test_env/$test_name
cp log/test_log.txt test/test_output.txt /irods_test_env/$test_name
[ -f /var/log/irods/irods.log ] && cp /var/log/irods/irods.log /irods_test_env/$test_name

if [ "$1" = 'Ubuntu_16' ]; then
   cp -r /irods_test_env/* /irods_build/Ubuntu_16/
fi

# Keep container running if the test fails.
if [[ $ec != 0 ]]; then
    #tail -f /dev/null
    # Is this better? sleep 2147483647d
    exit $ec
    #return $ec
fi 
