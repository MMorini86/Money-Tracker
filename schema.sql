drop table if exists entries;
create table entries (
  id integer primary key autoincrement,
  data date,
  category text not null,
  item text not null,
  amount REAL
);
