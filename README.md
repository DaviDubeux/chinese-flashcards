# Flashcards de Hanzi para o Notion

Dois scripts Python pequenos para um banco de dados de flashcards no Notion:

- **`fill_card.py`** pega a palavra do campo **Hanzi** de um card e preenche o resto: uma **capa** com os caracteres, o **Pinyin** (por exemplo `wǒ`) e o nível **HSK** (por exemplo `HSK-1`).
- **`pick_random.py`** marca 10 cards aleatórios para revisar: 5 **Difícil**, 3 **Médio** e 2 **Fácil**.

Você pode rodar os dois no seu computador, sem servidor e sem webhooks. Se quiser que rodem sozinhos a partir do Notion, veja [Automatizar com webhooks do Notion](#automatizar-com-webhooks-do-notion) logo depois.

![Exemplo de capa](example_cover.png)

## Rodar os scripts no seu computador

### Configuração (só uma vez)
1. **Crie uma integração do Notion.** Acesse https://www.notion.so/profile/integrations, crie uma integração interna e copie o segredo dela (começa com `ntn_`).
2. **Dê acesso ao seu banco de dados.** Abra o banco de flashcards no Notion, clique em **•••** › **Conexões** e adicione a sua integração.
3. **Copie o id do banco de dados.** São os 32 caracteres do link do banco, antes de `?v=`: `notion.so/`**`1a2b3c...`**`?v=...`
4. **Instale o Python 3 e as dependências**, a partir desta pasta:
   ```
   pip install -r requirements.txt
   ```
5. **Defina o segredo e o id do banco** no terminal onde você vai rodar os scripts:
   ```
   export NOTION_TOKEN=ntn_...
   export NOTION_DATABASE_ID=1a2b3c...
   ```
   No PowerShell do Windows, use `$env:NOTION_TOKEN="ntn_..."`.

O banco precisa de um campo **Hanzi** (título ou texto). **Pinyin** (texto) e **HSK** (seleção, texto ou número) são preenchidos se existirem. Para usar outros nomes de coluna, mude as configurações no topo de `hanzi_covers.py`.

### Preencher cards: `fill_card.py`
```
python3 fill_card.py --all            # todos os cards: preenche Pinyin e HSK, cria as capas que faltam
python3 fill_card.py --all --force    # o mesmo, e redesenha todas as capas
```
A primeira execução baixa a fonte (26 MB) e a lista de palavras do HSK, uma vez só.

Para preencher só alguns cards, passe os links deles no lugar de `--all`. Assim as capas são sempre redesenhadas.
1. No Notion, abra o card, clique em **•••** no canto superior direito e escolha **Copiar link**.
2. Cole o link depois do nome do script, **entre aspas**:
   ```
   python3 fill_card.py "https://www.notion.so/me/学习-1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d?pvs=4"
   ```
   As aspas são importantes: sem elas, o `?` do link faz o terminal do macOS responder `no matches found`.
3. Para vários cards, coloque mais links separados por espaço. O id de 32 caracteres no fim do link também funciona sozinho.

### Escolher cards para revisar: `pick_random.py`
```
python3 pick_random.py --reset    # desmarca o grupo anterior e marca 10 cards novos
python3 pick_random.py            # marca mais 10, mantendo os que já estão marcados
```
O script marca a caixa **Revisar** em 5 cards **Difícil**, 3 **Médio** e 2 **Fácil**, de acordo com a propriedade **Status**. Cards já marcados, ou com outro status, nunca são escolhidos.

Se um status não tiver cards suficientes, o próximo status mais difícil completa, depois o próximo mais fácil. Por exemplo, com só 4 cards Difícil você recebe 4 Difícil + 4 Médio + 2 Fácil.

| Opção | Padrão | O que faz |
|---|---|---|
| `--prop` | `Revisar` | A propriedade a marcar. Funciona com caixa de seleção, seleção, status, seleção múltipla, texto, número e data. |
| `--value` | marcado / hoje | O valor a definir. |
| `--by` | `Status` | A propriedade de dificuldade (status ou seleção). |
| `--mix` | `Difícil:5,Médio:3,Fácil:2` | Quantos cards de cada, do mais difícil para o mais fácil. |
| `--n` | | `--n 10` escolhe 10 cards aleatórios e ignora a dificuldade. |
| `--reset` | | Primeiro limpa a propriedade em todos os cards. Propriedades de status não podem ser limpas. |
| `--db` | `NOTION_DATABASE_ID` | O id do banco de dados. |

### Ver uma capa antes
```
python3 hanzi_covers.py --preview 你好
```
Isso gera `preview.png` sem mexer no Notion.

## Automatizar com webhooks do Notion
O Notion pode chamar esses mesmos scripts por você: uma automação preenche cada card novo, e um botão escolhe os cards para revisar. Para isso, o `server.py` precisa rodar num lugar que o Notion alcance. Estes passos usam o plano gratuito do [Render](https://render.com).

### 1. Hospedar o servidor
1. Envie esta pasta para um repositório no GitHub.
2. No Render, crie um **Web Service** a partir desse repositório, com o comando de início `python3 server.py`. Ele publica de novo a cada push.
3. Em **Environment** no Render, adicione:
   - `NOTION_TOKEN`: o segredo da sua integração
   - `WEBHOOK_KEY`: qualquer palavra longa e aleatória que você escolher. Ela impede que estranhos usem o seu servidor.
   - `NOTION_DATABASE_ID`: opcional, o id do banco de flashcards

Os links de webhook abaixo usam `https://SEU-APP.onrender.com`; troque pelo endereço do seu Render, e `SUA_WEBHOOK_KEY` pela sua chave.

### 2. Preencher cards novos automaticamente
No banco de flashcards, clique em **⚡** (Automações) › **Nova automação**:
- **Gatilho:** *Página adicionada* ou *Hanzi editado*, para que Pinyin, HSK e capa acompanhem as mudanças.
- **Ação:** *Enviar webhook* para `https://SEU-APP.onrender.com/?key=SUA_WEBHOOK_KEY`

Isso roda o `fill_card.py` no card. Uma correção manual no Pinyin fica até você editar o Hanzi daquele card de novo.

### 3. Botão de revisão
Adicione um **Botão** em qualquer lugar do Notion, dentro do banco ou em outra página, com a ação *Enviar webhook* para:
```
https://SEU-APP.onrender.com/random?key=SUA_WEBHOOK_KEY&reset=1
```
Isso roda `pick_random.py --reset`. O link aceita as mesmas opções sem os traços, por exemplo `&n=10` ou `&mix=Difícil:6,Médio:4`. Se o botão não estiver dentro do banco, o servidor usa `NOTION_DATABASE_ID`, ou então procura o banco compartilhado com a sua integração que tem a propriedade **Revisar**.

Se um webhook não fizer nada, veja os **Logs** no Render. Um card preenchido aparece como `✓ 我 wǒ | HSK-1`, e uma escolha de revisão como `✓ revisão: Revisar=true em 10 cards ...`.

## Configurações (topo de `hanzi_covers.py`)
| Configuração | Padrão | O que faz |
|---|---|---|
| `HANZI_PROP`, `PINYIN_PROP`, `HSK_PROP` | `Hanzi`, `Pinyin`, `HSK` | Os nomes das suas colunas. |
| `HSK_VERSION` | `"n"` (HSK 3.0, níveis 1–7) | Use `"o"` para o HSK 2.0 (níveis 1–6). |
| `FILL_ONLY_EMPTY` | `False` | Use `True` para nunca sobrescrever Pinyin ou HSK já preenchidos. |
| `SHOW_PINYIN` | `False` | Mostra o pinyin na capa. |

## De onde vêm os dados
- **Pinyin:** [pypinyin](https://github.com/mozillazg/python-pinyin) (licença MIT), que lê a palavra inteira para dar o tom certo a cada caractere no contexto (晚上好 → wǎn shàng hǎo).
- **Nível HSK:** a lista [Complete HSK Vocabulary](https://github.com/drkameleon/complete-hsk-vocabulary) (licença MIT, cerca de 11.000 palavras), baixada uma vez como `hsk.json`. Palavras fora da lista ficam sem nível HSK.
- **Fonte da capa:** [LXGW WenKai GB](https://github.com/lxgw/LxgwWenKaiGB) (SIL Open Font License), então as capas podem ser compartilhadas livremente.

## Limitações conhecidas
- **O pinyin fica em minúsculas, com uma sílaba por caractere,** por exemplo *zhōng guó*. Nomes próprios não ganham maiúscula.
- **O primeiro webhook depois de uma pausa pode demorar.** O plano gratuito do Render dorme depois de uns 15 minutos sem uso e leva até um minuto para acordar.

## Licença
Código sob a [licença MIT](LICENSE): você pode usar, modificar e compartilhar à vontade, mantendo o aviso de copyright.
