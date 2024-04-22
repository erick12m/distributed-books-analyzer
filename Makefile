SHELL := /bin/bash
PWD := $(shell pwd)

docker-image:
	#
	# TODO: Add corresponding build commands per process
	#

	# Execute this command from time to time to clean up intermediate stages generated
	# during client build. Don't leave uncommented to avoid rebuilding the client image every 
	# time the docker-compose-up command is executed, even when client code has not changed
	# docker rmi `docker images --filter label=intermediateStageToBeDeleted=true -q`
.PHONY: docker-image

docker-compose-up: docker-image
	docker compose -f docker-compose.yaml up -d --build --remove-orphans
.PHONY: docker-compose-up

docker-compose-down:
	docker compose -f docker-compose.yaml stop -t 3
	docker compose -f docker-compose.yaml down
.PHONY: docker-compose-down

docker-compose-logs:
	docker compose -f docker-compose.yaml logs -f
.PHONY: docker-compose-logs