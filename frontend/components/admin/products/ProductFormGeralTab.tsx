"use client";

import React from "react";
import { resolveImageUrl, type NovaImagem } from "@/lib/hooks/useProductFormCampos";
import type { AdminProduct, AdminProductImage } from "@/lib/types/adminProducts";

const inputCls =
  "mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

function MiniaturaImagem({
  src,
  alt,
  padrao,
  desabilitado,
  opaca,
  tituloRemover,
  onPadrao,
  onRemover,
}: {
  src: string;
  alt: string;
  padrao: boolean;
  desabilitado: boolean;
  opaca?: boolean;
  tituloRemover: string;
  onPadrao: () => void;
  onRemover: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={`group relative h-14 w-14 overflow-hidden rounded border bg-white ${
          padrao ? "border-amber-500 ring-2 ring-amber-300" : "border-gray-200"
        } ${opaca ? "opacity-40" : ""}`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt={alt} className="h-full w-full object-cover" />
        <button
          type="button"
          disabled={desabilitado}
          onClick={onRemover}
          title={tituloRemover}
          className="absolute inset-0 flex items-center justify-center bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity disabled:cursor-not-allowed cursor-pointer"
        >
          {opaca ? "⏳" : "🗑️"}
        </button>
      </div>
      <button
        type="button"
        disabled={desabilitado || padrao}
        onClick={onPadrao}
        title={padrao ? "Foto padrão" : "Usar como foto padrão"}
        className={`text-[10px] font-semibold ${
          padrao ? "text-amber-600" : "text-gray-500 hover:text-amber-600 cursor-pointer"
        }`}
      >
        {padrao ? "★ Padrão" : "☆ Padrão"}
      </button>
    </div>
  );
}

function ProductImageSection({
  produtoParaEditar,
  imagemPreview,
  imagens,
  novasImagens,
  chavePadrao,
  deletingImageId,
  saving,
  onImageChange,
  onRemoverImagem,
  onRemoverNovaImagem,
  onPadrao,
}: Pick<
  ProductFormGeralTabProps,
  | "produtoParaEditar"
  | "imagemPreview"
  | "imagens"
  | "novasImagens"
  | "chavePadrao"
  | "deletingImageId"
  | "saving"
  | "onImageChange"
  | "onRemoverImagem"
  | "onRemoverNovaImagem"
  | "onPadrao"
>) {
  const existentes = produtoParaEditar ? imagens : [];
  const total = existentes.length + novasImagens.length;
  return (
    <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-blue-900">
            Fotos do Produto &amp; Catálogo Visual CLIP
          </h4>
          <p className="text-xs text-blue-700">
            Adicione uma foto por vez; a marcada como padrão é a que aparece no catálogo e no chat.
            Cada foto é vetorizada automaticamente no Qdrant para reconhecimento por foto.
          </p>
        </div>
        {imagemPreview && (
          <div className="relative h-16 w-16 shrink-0 overflow-hidden rounded-lg border border-gray-200 bg-white">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={imagemPreview} alt="Preview" className="h-full w-full object-cover" />
          </div>
        )}
      </div>
      <div className="mt-3">
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          onChange={onImageChange}
          className="block w-full text-xs text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-blue-600 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-blue-700 cursor-pointer"
        />
      </div>
      {total > 0 && (
        <div className="mt-3">
          <span className="text-xs font-semibold text-gray-700">Imagens associadas ({total}):</span>
          <div className="mt-2 flex flex-wrap gap-3">
            {existentes.map((img) => (
              <MiniaturaImagem
                key={img.id}
                src={resolveImageUrl(img.imagem_url) ?? ""}
                alt="Foto cadastrada"
                padrao={chavePadrao === `e:${img.id}`}
                desabilitado={deletingImageId !== null || saving}
                opaca={deletingImageId === img.id}
                tituloRemover="Remover imagem do produto e do CLIP"
                onPadrao={() => onPadrao(`e:${img.id}`)}
                onRemover={() => onRemoverImagem(img.id)}
              />
            ))}
            {novasImagens.map((nova) => (
              <MiniaturaImagem
                key={nova.chave}
                src={nova.preview}
                alt="Foto a enviar"
                padrao={chavePadrao === nova.chave}
                desabilitado={saving}
                tituloRemover="Descartar foto (ainda não enviada)"
                onPadrao={() => onPadrao(nova.chave)}
                onRemover={() => onRemoverNovaImagem(nova.chave)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface ProductFormGeralTabProps {
  produtoParaEditar?: AdminProduct | null;
  nome: string;
  categoria: string;
  familia: string;
  preco: string;
  precoBaseFornecedor: string;
  diasAlertaEstoque: string;
  descricao: string;
  especificacoesTecnicas: string;
  dimensoesCm: string;
  pesoKg: string;
  imagemPreview: string | null;
  imagens: AdminProductImage[];
  novasImagens: NovaImagem[];
  chavePadrao: string | null;
  deletingImageId: number | null;
  saving: boolean;
  onNome: (v: string) => void;
  onCategoria: (v: string) => void;
  onFamilia: (v: string) => void;
  onPreco: (v: string) => void;
  onPrecoBase: (v: string) => void;
  onDiasAlerta: (v: string) => void;
  onDescricao: (v: string) => void;
  onEspecificacoes: (v: string) => void;
  onDimensoes: (v: string) => void;
  onPeso: (v: string) => void;
  onImageChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoverImagem: (id: number) => void;
  onRemoverNovaImagem: (chave: string) => void;
  onPadrao: (chave: string) => void;
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => void;
}

function CampoAreaTexto({
  rotulo,
  value,
  onChange,
  placeholder,
}: {
  rotulo: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
        {rotulo}
      </label>
      <textarea
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={inputCls}
      />
    </div>
  );
}

function CamposMedidas({
  dimensoesCm,
  pesoKg,
  onDimensoes,
  onPeso,
}: {
  dimensoesCm: string;
  pesoKg: string;
  onDimensoes: (v: string) => void;
  onPeso: (v: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div>
        <label
          htmlFor="produto-dimensoes"
          className="block text-xs font-semibold text-gray-700 uppercase tracking-wider"
        >
          Dimensões (L x A x P, cm)
        </label>
        <input
          id="produto-dimensoes"
          type="text"
          maxLength={120}
          value={dimensoesCm}
          onChange={(e) => onDimensoes(e.target.value)}
          placeholder="Ex: 12 x 8 x 3"
          className={inputCls}
        />
      </div>
      <div>
        <label
          htmlFor="produto-peso"
          className="block text-xs font-semibold text-gray-700 uppercase tracking-wider"
        >
          Peso (kg)
        </label>
        <input
          id="produto-peso"
          type="number"
          step="0.001"
          min="0"
          value={pesoKg}
          onChange={(e) => onPeso(e.target.value)}
          placeholder="Ex: 0,350"
          className={inputCls}
        />
      </div>
    </div>
  );
}

function RodapeAcoes({
  saving,
  editando,
  onClose,
}: {
  saving: boolean;
  editando: boolean;
  onClose: () => void;
}) {
  return (
    <div className="flex items-center justify-end gap-3 border-t border-gray-100 pt-4">
      <button
        type="button"
        onClick={onClose}
        disabled={saving}
        className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 cursor-pointer"
      >
        Cancelar
      </button>
      <button
        type="submit"
        disabled={saving}
        className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
      >
        {saving ? "Salvando..." : editando ? "Atualizar Dados" : "Salvar Produto"}
      </button>
    </div>
  );
}

function CamposPreco({
  precoBaseFornecedor,
  preco,
  onPrecoBase,
  onPreco,
}: {
  precoBaseFornecedor: string;
  preco: string;
  onPrecoBase: (v: string) => void;
  onPreco: (v: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2">
      <div>
        <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
          Preço Revendedor
        </label>
        <input
          type="number"
          step="0.01"
          min="0"
          value={precoBaseFornecedor}
          onChange={(e) => onPrecoBase(e.target.value)}
          placeholder="R$ 0,00"
          className={inputCls}
        />
      </div>
      <div>
        <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
          Preço Venda *
        </label>
        <input
          type="number"
          step="0.01"
          min="0"
          required
          value={preco}
          onChange={(e) => onPreco(e.target.value)}
          placeholder="R$ 0,00"
          className={`${inputCls} font-semibold text-gray-900`}
        />
      </div>
    </div>
  );
}

export function ProductFormGeralTab({
  produtoParaEditar,
  nome,
  categoria,
  familia,
  preco,
  precoBaseFornecedor,
  diasAlertaEstoque,
  descricao,
  especificacoesTecnicas,
  dimensoesCm,
  pesoKg,
  imagemPreview,
  imagens,
  novasImagens,
  chavePadrao,
  deletingImageId,
  saving,
  onNome,
  onCategoria,
  onFamilia,
  onPreco,
  onPrecoBase,
  onDiasAlerta,
  onDescricao,
  onEspecificacoes,
  onDimensoes,
  onPeso,
  onImageChange,
  onRemoverImagem,
  onRemoverNovaImagem,
  onPadrao,
  onClose,
  onSubmit,
}: ProductFormGeralTabProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
            Nome do Produto *
          </label>
          <input
            type="text"
            required
            value={nome}
            onChange={(e) => onNome(e.target.value)}
            placeholder="Ex: Gravador IP NVD 1016"
            className={inputCls}
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
            Categoria
          </label>
          <input
            type="text"
            list="categorias-list"
            value={categoria}
            onChange={(e) => onCategoria(e.target.value)}
            placeholder="Ex: CFTV"
            className={inputCls}
          />
          <datalist id="categorias-list">
            <option value="CFTV" />
            <option value="Alarmes" />
            <option value="Redes" />
            <option value="Controle de Acesso" />
            <option value="Automação" />
            <option value="Geral" />
          </datalist>
        </div>

        <div>
          <label
            htmlFor="produto-familia"
            className="block text-xs font-semibold text-gray-700 uppercase tracking-wider"
          >
            Família
          </label>
          <input
            id="produto-familia"
            type="text"
            maxLength={120}
            value={familia}
            onChange={(e) => onFamilia(e.target.value)}
            placeholder="Ex: iDAccess"
            className={inputCls}
          />
          <p className="mt-1 text-[11px] text-gray-500">
            Agrupa os modelos do mesmo produto. Cada modelo continua sendo um produto, com preço e
            estoque próprios. Opcional.
          </p>
        </div>

        <CamposPreco
          precoBaseFornecedor={precoBaseFornecedor}
          preco={preco}
          onPrecoBase={onPrecoBase}
          onPreco={onPreco}
        />

        <div>
          <label
            htmlFor="produto-dias-alerta-estoque"
            className="block text-xs font-semibold text-gray-700 uppercase tracking-wider"
          >
            Alertar estoque com (dias)
          </label>
          <input
            id="produto-dias-alerta-estoque"
            type="number"
            step="1"
            min="1"
            max="365"
            value={diasAlertaEstoque}
            onChange={(e) => onDiasAlerta(e.target.value)}
            placeholder="Padrão do sistema (10)"
            className={inputCls}
          />
          <p className="mt-1 text-[11px] text-gray-500">
            O agente avisa quando a previsão de estoque cair abaixo disto. Use o prazo de
            reposição/entrega deste produto; vazio usa o padrão.
          </p>
        </div>
      </div>

      <CampoAreaTexto
        rotulo="Descrição Comercial"
        value={descricao}
        onChange={onDescricao}
        placeholder="Descrição do produto para o catálogo e assistente de vendas..."
      />

      <CampoAreaTexto
        rotulo="Especificações Técnicas"
        value={especificacoesTecnicas}
        onChange={onEspecificacoes}
        placeholder="Canais, resolução, alcance IR, voltagem, portas..."
      />

      <CamposMedidas
        dimensoesCm={dimensoesCm}
        pesoKg={pesoKg}
        onDimensoes={onDimensoes}
        onPeso={onPeso}
      />

      <ProductImageSection
        produtoParaEditar={produtoParaEditar}
        imagemPreview={imagemPreview}
        imagens={imagens}
        novasImagens={novasImagens}
        chavePadrao={chavePadrao}
        deletingImageId={deletingImageId}
        saving={saving}
        onImageChange={onImageChange}
        onRemoverImagem={onRemoverImagem}
        onRemoverNovaImagem={onRemoverNovaImagem}
        onPadrao={onPadrao}
      />

      <RodapeAcoes saving={saving} editando={Boolean(produtoParaEditar)} onClose={onClose} />
    </form>
  );
}
