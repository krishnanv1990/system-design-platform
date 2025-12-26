/**
 * Interactive database schema editor component
 * Visual builder for defining database schemas with multiple store types
 */

import { useState, useEffect, useCallback } from "react"
import {
  Plus,
  Trash2,
  Database,
  Key,
  FileJson,
  GitBranch,
  Table2,
  ChevronDown,
  ChevronUp,
  GripVertical,
  Columns,
  Hash,
  Type,
  Calendar,
  ToggleLeft,
  Sparkles,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

// Database types with their icons and colors
const DATABASE_TYPES = [
  {
    id: "sql",
    name: "SQL Database",
    description: "Relational database with tables and foreign keys",
    icon: Table2,
    color: "from-blue-500 to-blue-600",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30",
    examples: "PostgreSQL, MySQL, SQLite",
  },
  {
    id: "kv",
    name: "Key-Value Store",
    description: "Fast lookups by key, ideal for caching",
    icon: Key,
    color: "from-amber-500 to-orange-500",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30",
    examples: "Redis, Memcached, DynamoDB",
  },
  {
    id: "document",
    name: "Document Store",
    description: "Flexible JSON documents, schema-less",
    icon: FileJson,
    color: "from-emerald-500 to-green-600",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/30",
    examples: "MongoDB, CouchDB, Firestore",
  },
  {
    id: "graph",
    name: "Graph Database",
    description: "Relationships between entities as first-class",
    icon: GitBranch,
    color: "from-purple-500 to-violet-600",
    bgColor: "bg-purple-500/10",
    borderColor: "border-purple-500/30",
    examples: "Neo4j, Neptune, ArangoDB",
  },
  {
    id: "timeseries",
    name: "Time Series",
    description: "Optimized for time-stamped data",
    icon: Calendar,
    color: "from-cyan-500 to-teal-600",
    bgColor: "bg-cyan-500/10",
    borderColor: "border-cyan-500/30",
    examples: "InfluxDB, TimescaleDB, Prometheus",
  },
  {
    id: "search",
    name: "Search Engine",
    description: "Full-text search and analytics",
    icon: Sparkles,
    color: "from-pink-500 to-rose-600",
    bgColor: "bg-pink-500/10",
    borderColor: "border-pink-500/30",
    examples: "Elasticsearch, Algolia, Meilisearch",
  },
] as const

type DatabaseType = typeof DATABASE_TYPES[number]["id"]

// Column types for SQL databases
const SQL_COLUMN_TYPES = [
  { value: "uuid", label: "UUID", icon: Hash },
  { value: "serial", label: "Serial/Auto-increment", icon: Hash },
  { value: "integer", label: "Integer", icon: Hash },
  { value: "bigint", label: "Big Integer", icon: Hash },
  { value: "varchar", label: "Varchar", icon: Type },
  { value: "text", label: "Text", icon: Type },
  { value: "boolean", label: "Boolean", icon: ToggleLeft },
  { value: "timestamp", label: "Timestamp", icon: Calendar },
  { value: "date", label: "Date", icon: Calendar },
  { value: "json", label: "JSON", icon: FileJson },
  { value: "decimal", label: "Decimal", icon: Hash },
  { value: "float", label: "Float", icon: Hash },
]

// Field types for other database types
const FIELD_TYPES = {
  kv: [
    { value: "string", label: "String" },
    { value: "number", label: "Number" },
    { value: "json", label: "JSON Object" },
    { value: "list", label: "List" },
    { value: "set", label: "Set" },
    { value: "hash", label: "Hash Map" },
  ],
  document: [
    { value: "string", label: "String" },
    { value: "number", label: "Number" },
    { value: "boolean", label: "Boolean" },
    { value: "object", label: "Nested Object" },
    { value: "array", label: "Array" },
    { value: "date", label: "Date" },
    { value: "objectId", label: "Object ID" },
  ],
  graph: [
    { value: "string", label: "String" },
    { value: "number", label: "Number" },
    { value: "boolean", label: "Boolean" },
    { value: "date", label: "Date" },
    { value: "list", label: "List" },
  ],
  timeseries: [
    { value: "timestamp", label: "Timestamp" },
    { value: "float", label: "Float" },
    { value: "integer", label: "Integer" },
    { value: "string", label: "Tag (String)" },
    { value: "boolean", label: "Boolean" },
  ],
  search: [
    { value: "text", label: "Text (Analyzed)" },
    { value: "keyword", label: "Keyword (Exact)" },
    { value: "number", label: "Number" },
    { value: "date", label: "Date" },
    { value: "boolean", label: "Boolean" },
    { value: "object", label: "Nested Object" },
  ],
}

interface Column {
  id: string
  name: string
  type: string
  constraints: string[]
  description: string
}

interface TableStore {
  id: string
  name: string
  dbType: DatabaseType
  description: string
  columns: Column[]
  indexes: string[]
  expanded: boolean
}

interface SchemaEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
}

// Generate unique ID
const generateId = () => Math.random().toString(36).substr(2, 9)

// Parse JSON schema to internal format
const parseSchema = (jsonStr: string): TableStore[] => {
  try {
    const data = JSON.parse(jsonStr)
    if (data.stores && Array.isArray(data.stores)) {
      return data.stores.map((store: any) => ({
        id: generateId(),
        name: store.name || "",
        dbType: store.type || "sql",
        description: store.description || "",
        columns: (store.fields || store.columns || []).map((col: any) => ({
          id: generateId(),
          name: col.name || "",
          type: col.type || "varchar",
          constraints: col.constraints || [],
          description: col.description || "",
        })),
        indexes: store.indexes || [],
        expanded: true,
      }))
    }
    // Legacy format
    if (data.tables) {
      return Object.entries(data.tables).map(([name, table]: [string, any]) => ({
        id: generateId(),
        name,
        dbType: "sql" as DatabaseType,
        description: "",
        columns: Object.entries(table.columns || {}).map(([colName, col]: [string, any]) => ({
          id: generateId(),
          name: colName,
          type: typeof col === "string" ? col : col.type || "varchar",
          constraints: [
            col.primary_key && "primary_key",
            col.unique && "unique",
            col.nullable === false && "not_null",
          ].filter(Boolean) as string[],
          description: "",
        })),
        indexes: table.indexes || [],
        expanded: true,
      }))
    }
    return []
  } catch {
    return []
  }
}

// Convert internal format to JSON
const toJsonSchema = (stores: TableStore[]): string => {
  const schema = {
    stores: stores.map((store) => ({
      name: store.name,
      type: store.dbType,
      description: store.description,
      fields: store.columns.map((col) => ({
        name: col.name,
        type: col.type,
        constraints: col.constraints,
        description: col.description,
      })),
      indexes: store.indexes,
    })),
  }
  return JSON.stringify(schema, null, 2)
}

export default function SchemaEditor({
  value,
  onChange,
  readOnly = false,
}: SchemaEditorProps) {
  const [stores, setStores] = useState<TableStore[]>([])
  const [showTypeSelector, setShowTypeSelector] = useState(false)

  // Parse initial value
  useEffect(() => {
    if (value) {
      const parsed = parseSchema(value)
      if (parsed.length > 0) {
        setStores(parsed)
      }
    }
  }, [])

  // Update parent when stores change
  const updateParent = useCallback(
    (newStores: TableStore[]) => {
      setStores(newStores)
      onChange(toJsonSchema(newStores))
    },
    [onChange]
  )

  const addStore = (dbType: DatabaseType) => {
    const newStore: TableStore = {
      id: generateId(),
      name: "",
      dbType,
      description: "",
      columns: [
        {
          id: generateId(),
          name: dbType === "sql" ? "id" : "key",
          type: dbType === "sql" ? "uuid" : "string",
          constraints: dbType === "sql" ? ["primary_key"] : [],
          description: dbType === "sql" ? "Primary key" : "Unique identifier",
        },
      ],
      indexes: [],
      expanded: true,
    }
    updateParent([...stores, newStore])
    setShowTypeSelector(false)
  }

  const removeStore = (storeId: string) => {
    updateParent(stores.filter((s) => s.id !== storeId))
  }

  const updateStore = (storeId: string, updates: Partial<TableStore>) => {
    updateParent(
      stores.map((s) => (s.id === storeId ? { ...s, ...updates } : s))
    )
  }

  const toggleExpand = (storeId: string) => {
    setStores(
      stores.map((s) =>
        s.id === storeId ? { ...s, expanded: !s.expanded } : s
      )
    )
  }

  const addColumn = (storeId: string) => {
    const store = stores.find((s) => s.id === storeId)
    if (!store) return

    const newColumn: Column = {
      id: generateId(),
      name: "",
      type: store.dbType === "sql" ? "varchar" : "string",
      constraints: [],
      description: "",
    }

    updateParent(
      stores.map((s) =>
        s.id === storeId ? { ...s, columns: [...s.columns, newColumn] } : s
      )
    )
  }

  const removeColumn = (storeId: string, columnId: string) => {
    updateParent(
      stores.map((s) =>
        s.id === storeId
          ? { ...s, columns: s.columns.filter((c) => c.id !== columnId) }
          : s
      )
    )
  }

  const updateColumn = (
    storeId: string,
    columnId: string,
    updates: Partial<Column>
  ) => {
    updateParent(
      stores.map((s) =>
        s.id === storeId
          ? {
              ...s,
              columns: s.columns.map((c) =>
                c.id === columnId ? { ...c, ...updates } : c
              ),
            }
          : s
      )
    )
  }

  const toggleConstraint = (
    storeId: string,
    columnId: string,
    constraint: string
  ) => {
    const store = stores.find((s) => s.id === storeId)
    const column = store?.columns.find((c) => c.id === columnId)
    if (!column) return

    const newConstraints = column.constraints.includes(constraint)
      ? column.constraints.filter((c) => c !== constraint)
      : [...column.constraints, constraint]

    updateColumn(storeId, columnId, { constraints: newConstraints })
  }

  const getFieldTypes = (dbType: DatabaseType) => {
    if (dbType === "sql") return SQL_COLUMN_TYPES
    return (FIELD_TYPES[dbType] || FIELD_TYPES.document).map((t) => ({
      ...t,
      icon: Type,
    }))
  }

  const getDbTypeInfo = (dbType: DatabaseType) =>
    DATABASE_TYPES.find((t) => t.id === dbType)!

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
            Data Storage Schema
          </h3>
          <p className="text-sm text-muted-foreground">
            Define your data stores, tables, and their structures
          </p>
        </div>
        {!readOnly && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowTypeSelector(!showTypeSelector)}
            className="gap-2 border-dashed hover:border-primary hover:bg-primary/5"
          >
            <Plus className="h-4 w-4" />
            Add Data Store
          </Button>
        )}
      </div>

      {/* Database Type Selector */}
      {showTypeSelector && (
        <Card className="border-2 border-dashed border-primary/30 bg-gradient-to-br from-primary/5 to-transparent animate-fade-in">
          <CardContent className="pt-4">
            <p className="text-sm font-medium mb-3 text-muted-foreground">
              Choose a database type:
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {DATABASE_TYPES.map((db) => (
                <button
                  key={db.id}
                  onClick={() => addStore(db.id)}
                  className={cn(
                    "group relative flex flex-col items-start p-4 rounded-xl border-2 transition-all duration-200",
                    "hover:scale-[1.02] hover:shadow-lg",
                    db.borderColor,
                    db.bgColor,
                    "hover:border-opacity-100"
                  )}
                >
                  <div
                    className={cn(
                      "p-2 rounded-lg bg-gradient-to-br mb-2",
                      db.color
                    )}
                  >
                    <db.icon className="h-5 w-5 text-white" />
                  </div>
                  <span className="font-medium text-sm">{db.name}</span>
                  <span className="text-xs text-muted-foreground mt-1 text-left">
                    {db.description}
                  </span>
                  <span className="text-[10px] text-muted-foreground/70 mt-2">
                    {db.examples}
                  </span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {stores.length === 0 && !showTypeSelector && (
        <Card className="border-2 border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <div className="p-4 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 mb-4">
              <Database className="h-8 w-8 text-primary" />
            </div>
            <p className="text-muted-foreground text-center mb-4">
              No data stores defined yet.
              <br />
              Click "Add Data Store" to get started.
            </p>
            <Button
              variant="outline"
              onClick={() => setShowTypeSelector(true)}
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              Add Your First Store
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Store Cards */}
      <div className="space-y-4">
        {stores.map((store) => {
          const dbInfo = getDbTypeInfo(store.dbType)
          const fieldTypes = getFieldTypes(store.dbType)

          return (
            <Card
              key={store.id}
              className={cn(
                "overflow-hidden transition-all duration-200",
                "border-l-4",
                dbInfo.borderColor.replace("border-", "border-l-")
              )}
            >
              {/* Store Header */}
              <div
                className={cn(
                  "flex items-center gap-3 p-4 cursor-pointer",
                  dbInfo.bgColor
                )}
                onClick={() => toggleExpand(store.id)}
              >
                <div className="flex items-center gap-2 text-muted-foreground">
                  <GripVertical className="h-4 w-4" />
                </div>
                <div
                  className={cn(
                    "p-2 rounded-lg bg-gradient-to-br",
                    dbInfo.color
                  )}
                >
                  <dbInfo.icon className="h-4 w-4 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={store.name}
                      onChange={(e) => {
                        e.stopPropagation()
                        updateStore(store.id, { name: e.target.value })
                      }}
                      onClick={(e) => e.stopPropagation()}
                      placeholder={
                        store.dbType === "sql"
                          ? "table_name"
                          : store.dbType === "kv"
                          ? "cache_name"
                          : "collection_name"
                      }
                      className={cn(
                        "bg-transparent font-medium text-base focus:outline-none focus:ring-2 focus:ring-primary/30 rounded px-2 py-1 -ml-2",
                        "placeholder:text-muted-foreground/50",
                        readOnly && "cursor-default"
                      )}
                      readOnly={readOnly}
                    />
                    <Badge variant="outline" className="text-xs shrink-0">
                      {dbInfo.name}
                    </Badge>
                  </div>
                  <input
                    type="text"
                    value={store.description}
                    onChange={(e) => {
                      e.stopPropagation()
                      updateStore(store.id, { description: e.target.value })
                    }}
                    onClick={(e) => e.stopPropagation()}
                    placeholder="What is this store used for?"
                    className={cn(
                      "w-full bg-transparent text-sm text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30 rounded px-2 py-1 -ml-2 mt-1",
                      "placeholder:text-muted-foreground/40",
                      readOnly && "cursor-default"
                    )}
                    readOnly={readOnly}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    {store.columns.length} field
                    {store.columns.length !== 1 ? "s" : ""}
                  </Badge>
                  {!readOnly && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive/70 hover:text-destructive hover:bg-destructive/10"
                      onClick={(e) => {
                        e.stopPropagation()
                        removeStore(store.id)
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                  {store.expanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </div>
              </div>

              {/* Store Content */}
              {store.expanded && (
                <CardContent className="pt-0 pb-4">
                  {/* Column Headers */}
                  <div className="grid grid-cols-12 gap-2 px-2 py-2 text-xs font-medium text-muted-foreground border-b mb-2">
                    <div className="col-span-3 flex items-center gap-1">
                      <Columns className="h-3 w-3" />
                      Field Name
                    </div>
                    <div className="col-span-3">Type</div>
                    <div className="col-span-3">
                      {store.dbType === "sql" ? "Constraints" : "Options"}
                    </div>
                    <div className="col-span-2">Description</div>
                    <div className="col-span-1"></div>
                  </div>

                  {/* Columns */}
                  <div className="space-y-2">
                    {store.columns.map((column) => (
                      <div
                        key={column.id}
                        className="grid grid-cols-12 gap-2 items-center p-2 rounded-lg hover:bg-muted/50 transition-colors group"
                      >
                        {/* Field Name */}
                        <div className="col-span-3">
                          <input
                            type="text"
                            value={column.name}
                            onChange={(e) =>
                              updateColumn(store.id, column.id, {
                                name: e.target.value,
                              })
                            }
                            placeholder="field_name"
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 placeholder:text-muted-foreground/50"
                            readOnly={readOnly}
                          />
                        </div>

                        {/* Type */}
                        <div className="col-span-3">
                          <select
                            value={column.type}
                            onChange={(e) =>
                              updateColumn(store.id, column.id, {
                                type: e.target.value,
                              })
                            }
                            className="w-full px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30"
                            disabled={readOnly}
                          >
                            {fieldTypes.map((type) => (
                              <option key={type.value} value={type.value}>
                                {type.label}
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Constraints */}
                        <div className="col-span-3 flex flex-wrap gap-1">
                          {store.dbType === "sql" && (
                            <>
                              <button
                                onClick={() =>
                                  toggleConstraint(
                                    store.id,
                                    column.id,
                                    "primary_key"
                                  )
                                }
                                disabled={readOnly}
                                className={cn(
                                  "px-2 py-1 text-xs rounded-md border transition-colors",
                                  column.constraints.includes("primary_key")
                                    ? "bg-amber-500/20 border-amber-500/50 text-amber-700 dark:text-amber-400"
                                    : "border-dashed border-muted-foreground/30 text-muted-foreground hover:border-amber-500/50"
                                )}
                              >
                                PK
                              </button>
                              <button
                                onClick={() =>
                                  toggleConstraint(
                                    store.id,
                                    column.id,
                                    "unique"
                                  )
                                }
                                disabled={readOnly}
                                className={cn(
                                  "px-2 py-1 text-xs rounded-md border transition-colors",
                                  column.constraints.includes("unique")
                                    ? "bg-blue-500/20 border-blue-500/50 text-blue-700 dark:text-blue-400"
                                    : "border-dashed border-muted-foreground/30 text-muted-foreground hover:border-blue-500/50"
                                )}
                              >
                                UQ
                              </button>
                              <button
                                onClick={() =>
                                  toggleConstraint(
                                    store.id,
                                    column.id,
                                    "not_null"
                                  )
                                }
                                disabled={readOnly}
                                className={cn(
                                  "px-2 py-1 text-xs rounded-md border transition-colors",
                                  column.constraints.includes("not_null")
                                    ? "bg-red-500/20 border-red-500/50 text-red-700 dark:text-red-400"
                                    : "border-dashed border-muted-foreground/30 text-muted-foreground hover:border-red-500/50"
                                )}
                              >
                                NN
                              </button>
                              <button
                                onClick={() =>
                                  toggleConstraint(
                                    store.id,
                                    column.id,
                                    "indexed"
                                  )
                                }
                                disabled={readOnly}
                                className={cn(
                                  "px-2 py-1 text-xs rounded-md border transition-colors",
                                  column.constraints.includes("indexed")
                                    ? "bg-green-500/20 border-green-500/50 text-green-700 dark:text-green-400"
                                    : "border-dashed border-muted-foreground/30 text-muted-foreground hover:border-green-500/50"
                                )}
                              >
                                IDX
                              </button>
                            </>
                          )}
                          {store.dbType !== "sql" && (
                            <>
                              <button
                                onClick={() =>
                                  toggleConstraint(
                                    store.id,
                                    column.id,
                                    "required"
                                  )
                                }
                                disabled={readOnly}
                                className={cn(
                                  "px-2 py-1 text-xs rounded-md border transition-colors",
                                  column.constraints.includes("required")
                                    ? "bg-red-500/20 border-red-500/50 text-red-700 dark:text-red-400"
                                    : "border-dashed border-muted-foreground/30 text-muted-foreground hover:border-red-500/50"
                                )}
                              >
                                Req
                              </button>
                              <button
                                onClick={() =>
                                  toggleConstraint(
                                    store.id,
                                    column.id,
                                    "indexed"
                                  )
                                }
                                disabled={readOnly}
                                className={cn(
                                  "px-2 py-1 text-xs rounded-md border transition-colors",
                                  column.constraints.includes("indexed")
                                    ? "bg-green-500/20 border-green-500/50 text-green-700 dark:text-green-400"
                                    : "border-dashed border-muted-foreground/30 text-muted-foreground hover:border-green-500/50"
                                )}
                              >
                                Idx
                              </button>
                            </>
                          )}
                        </div>

                        {/* Description */}
                        <div className="col-span-2">
                          <input
                            type="text"
                            value={column.description}
                            onChange={(e) =>
                              updateColumn(store.id, column.id, {
                                description: e.target.value,
                              })
                            }
                            placeholder="..."
                            className="w-full px-2 py-2 text-xs rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 placeholder:text-muted-foreground/30"
                            readOnly={readOnly}
                          />
                        </div>

                        {/* Actions */}
                        <div className="col-span-1 flex justify-end">
                          {!readOnly && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 opacity-0 group-hover:opacity-100 text-destructive/70 hover:text-destructive hover:bg-destructive/10 transition-opacity"
                              onClick={() => removeColumn(store.id, column.id)}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Add Column Button */}
                  {!readOnly && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => addColumn(store.id)}
                      className="mt-3 gap-2 text-muted-foreground hover:text-foreground"
                    >
                      <Plus className="h-4 w-4" />
                      Add Field
                    </Button>
                  )}
                </CardContent>
              )}
            </Card>
          )
        })}
      </div>

      {/* Summary Footer */}
      {stores.length > 0 && (
        <div className="flex items-center justify-between p-4 rounded-lg bg-muted/30 border">
          <div className="flex items-center gap-4">
            <div className="text-sm">
              <span className="font-medium">{stores.length}</span>
              <span className="text-muted-foreground">
                {" "}
                data store{stores.length !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="text-sm">
              <span className="font-medium">
                {stores.reduce((acc, s) => acc + s.columns.length, 0)}
              </span>
              <span className="text-muted-foreground"> total fields</span>
            </div>
          </div>
          <div className="flex gap-2">
            {Array.from(new Set(stores.map((s) => s.dbType))).map((type) => {
              const dbInfo = getDbTypeInfo(type)
              return (
                <Badge
                  key={type}
                  variant="outline"
                  className={cn("gap-1", dbInfo.bgColor)}
                >
                  <dbInfo.icon className="h-3 w-3" />
                  {stores.filter((s) => s.dbType === type).length}
                </Badge>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
