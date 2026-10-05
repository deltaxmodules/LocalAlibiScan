import express from 'express';
import { notesRouter } from './routes/notes';

const app = express();
app.use(express.json());
app.use('/notes', notesRouter);

app.get('/health', (_req, res) => {
  res.json({ ok: true });
});

app.listen(3000, () => {
  console.log('listening on 3000');
});
