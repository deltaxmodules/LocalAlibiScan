const fastify = require('fastify')();

fastify.get('/', async () => ({ hello: 'beta' }));

fastify.listen({ port: 3001 });
