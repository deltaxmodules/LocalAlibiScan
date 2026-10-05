import { Router } from 'express';
import { db } from '../db/database';

export const notesRouter = Router();

notesRouter.get('/', (_req, res) => {
  res.json(db.prepare('SELECT * FROM notes').all());
});

notesRouter.post('/', (req, res) => {
  const { title, body } = req.body;
  const info = db.prepare('INSERT INTO notes (title, body) VALUES (?, ?)').run(title, body);
  res.status(201).json({ id: info.lastInsertRowid });
});
