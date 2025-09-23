# Lista de Usuários do Sistema

Este documento contém a lista de usuários válidos para o sistema ELEIÇÕES CRORS - 2025.

## Regras de Geração

- **Usuário**: primeiro nome + último sobrenome (minúsculo, sem acentos, sem espaços)
- **Senha**: data de nascimento no formato ddmmaaaa

## Lista de Usuários

| Nome Completo | Usuário | Senha |
|---------------|---------|-------|
| André Nunes Flores | `andreflores` | `13051983` |
| Andréia Carla Viezzer | `andreiaviezzer` | `08061973` |
| Andressa Trápaga Paiz | `andressapaiz` | `11021990` |
| Bianca Carvalho Aguilar | `biancaaguilar` | `19121997` |
| Carina Reis Silveira | `carinasilveira` | `02011978` |
| Carlos Edvan Carvalho Duarte | `carlosduarte` | `16042001` |
| Clarissa da Costa Barcellos | `clarissabarcellos` | `16111987` |
| Cleonice Lourenço Guimarães Muller | `cleonicemuller` | `14091961` |
| Cristiano Grimaldi Boff | `cristianoboff` | `17031983` |
| Daniel José Bahi Aymone | `danielaymone` | `02051979` |
| Giovanna de Castro Bonamigo | `giovannabonamigo` | `30081994` |
| Gustavo Rodrigues Graminho | `gustavograminho` | `14061990` |
| Gustavo Santos de Barros | `gustavobarros` | `03052003` |
| Igor Ricardo de Souza Sansone | `igorsansone` | `30101987` |
| Jefferson Rocho Barth | `jeffersonbarth` | `15101985` |
| João Francisco Schmidt | `joaoschmidt` | `11071964` |
| João Paulo Melo de Carvalho | `joaocarvalho` | `24121980` |
| Jorge Miguel Chaves | `jorgechaves` | `01021958` |
| Leandro Oscar Collares da Silva | `leandrosilva` | `12091978` |
| Leonardo Carvalho da Rosa | `leonardorosa` | `31051984` |
| Leticia Pereira Voltz Alfaro | `leticiaalfaro` | `16021973` |
| Liliane Correa Bruno | `lilianebruno` | `10061984` |
| Luciano Dichel | `lucianodichel` | `26081981` |
| Luiza Gutheil Bayer | `luizabayer` | `19071993` |
| Matheus Prato da Silva | `matheussilva` | `09091998` |
| Marilda Zanella Busanello | `marildabusanello` | `06071963` |
| Rodrigo Fernandes Floriano | `rodrigofloriano` | `29071978` |
| Tânia Marli Mendes Leite | `tanialeite` | `19081962` |
| Tanise Barbosa Ramaswami | `taniseramaswami` | `15081991` |
| Tatiana de Carli da Silva | `tatianasilva` | `04051974` |
| Tatiana Nuñez Rosa | `tatianarosa` | `13081979` |
| Willians da Silva Marks | `williansmarks` | `22101983` |

**Total de usuários**: 32

## Notas Técnicas

- Os usuários são gerados automaticamente pela função `generate_users()` no arquivo `app.py`
- A autenticação substitui o sistema anterior de credenciais fixas (admin/senha123)
- Todas as funcionalidades de sessão e proteção de rotas permanecem inalteradas
- As senhas são baseadas nas datas de nascimento dos colaboradores fornecidas