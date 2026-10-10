DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gym_presence_app') THEN
        ALTER ROLE gym_presence_app WITH LOGIN PASSWORD 'gym_dev_password';
    ELSE
        CREATE ROLE gym_presence_app LOGIN PASSWORD 'gym_dev_password';
    END IF;
END
$$;

SELECT format('CREATE DATABASE gym_presence OWNER %I', 'gym_presence_app')
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = 'gym_presence'
)
\gexec

ALTER DATABASE gym_presence OWNER TO gym_presence_app;