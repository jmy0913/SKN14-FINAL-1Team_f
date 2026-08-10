import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator

from .models import Post, Comment, Card, ChatMessage
from .forms import CommentForm, PostForm


@login_required
def home_view(request):
    return render(request, "my_app/home.html")


@login_required
def main_chatbot_view(request):
    chat_sessions = request.user.chat_sessions.filter(mode="api")

    return render(request, "my_app/main_chatbot.html", {"chat_sessions": chat_sessions})


@login_required
def internal_docs_view(request):
    chat_sessions = request.user.chat_sessions.filter(mode="internal")

    return render(
        request, "my_app/internal_docs.html", {"chat_sessions": chat_sessions}
    )


def community_board_view(request):
    best_posts = (
        Post.objects.select_related("author")
        .filter(likes__gte=5)
        .order_by("-created_at")[:5]
    )

    best_post_ids = [post.id for post in best_posts]

    regular_posts_list = (
        Post.objects.select_related("author")
        .exclude(id__in=best_post_ids)
        .order_by("-created_at")
    )
    paginator = Paginator(regular_posts_list, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "best_posts": best_posts,
        "page_obj": page_obj,
    }
    return render(request, "my_app/community_board.html", context)


@login_required
def post_detail_view(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related("author").prefetch_related("comments__author"),
        id=post_id,
    )
    comment_form = CommentForm()

    if request.user.is_authenticated and request.user != post.author:
        post.views += 1
        post.save(update_fields=["views"])

    context = {
        "post": post,
        "comment_form": comment_form,
    }
    return render(request, "my_app/post_detail.html", context)


@login_required
@require_POST
def create_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
    return redirect("main:post-detail", post_id=post.id)


@login_required
@require_POST
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.user in post.likers.all():
        post.likers.remove(request.user)
        post.likes -= 1
    else:
        post.likers.add(request.user)
        post.likes += 1
    post.save()
    return JsonResponse({"new_likes": post.likes})


@login_required
@require_POST
def like_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user in comment.likers.all():
        comment.likers.remove(request.user)
        comment.likes -= 1
    else:
        comment.likers.add(request.user)
        comment.likes += 1
    comment.save()
    return JsonResponse({"new_likes": comment.likes})


@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user == comment.author or request.user.is_superuser:
        post_id = comment.post.id
        comment.delete()
        return redirect("main:post-detail", post_id=post_id)
    return HttpResponseForbidden()


@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user != comment.author and not request.user.is_superuser:
        return HttpResponseForbidden()
    if request.method == "POST":
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect("main:post-detail", post_id=comment.post.id)
    else:
        form = CommentForm(instance=comment)
    return render(
        request, "my_app/edit_comment.html", {"form": form, "comment": comment}
    )


@login_required
def create_post(request):
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect("main:post-detail", post_id=post.id)
    else:
        form = PostForm()
    return render(request, "my_app/create_post.html", {"form": form})


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.user != post.author and not request.user.is_superuser:
        return HttpResponseForbidden()
    if request.method == "POST":
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            return redirect("main:post-detail", post_id=post.id)
    else:
        form = PostForm(instance=post)
    return render(request, "my_app/edit_post.html", {"form": form, "post": post})


@login_required
@require_POST
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.user == post.author or request.user.is_superuser:
        post.delete()
        return redirect("main:community-board")
    return HttpResponseForbidden()


collection = None
doc_ids = []
doc_texts = []
okt = None


def ensure_search_initialized():
    global collection

    if collection is not None:
        return

    # 챗봇(apichat)이 서버 시작 시 이미 로드해 둔 벡터스토어를 재사용한다.
    # 같은 chroma_db 경로/컬렉션(google_api_docs)을 가리키므로,
    # 별도 PersistentClient와 임베딩 모델(bge-m3)을 다시 띄우지 않아도 된다.
    # (이전에는 첫 검색 요청 때 bge-m3를 처음 메모리에 올려서 느렸음)
    from apichat.utils.retriever_hybrid import _vs

    collection = _vs._collection


def normalize_meta(meta, default_doc=""):  # Chroma 메타데이터 정리
    raw_file = meta.get("source_file", "")
    if raw_file.endswith(".txt"):
        title = raw_file[:-4]
    else:
        title = meta.get("title") or raw_file or ""

    source = meta.get("url") or meta.get("source") or ""
    if isinstance(source, list):
        source = (source[0] or "").strip()
    elif isinstance(source, str):
        s = source.strip()
        if s[:1] in "[{":  # JSON 형태라면 url 추출
            try:
                data = json.loads(s)
                if isinstance(data, list) and data:
                    source = str(data[0]).strip()
                elif isinstance(data, dict) and "url" in data:
                    source = str(data["url"]).strip()
            except Exception:
                pass
        else:
            source = s

    snippet = (default_doc or "")[:220]

    return {
        "title": title,
        "source": source,
        "snippet": snippet,
    }


def search_dense(q, k):
    ensure_search_initialized()
    # 챗봇이 사용하는 것과 동일한(이미 로드된) 임베딩 객체로 쿼리를 임베딩한다.
    # 벡터스토어가 langchain Chroma라 chromadb 레벨 임베딩 함수가 없으므로
    # query_texts 대신 query_embeddings로 질의한다.
    from apichat.utils.retriever import embeddings

    res = collection.query(
        query_embeddings=[embeddings.embed_query(q)],
        n_results=k * 3,
        include=["documents", "metadatas"],
    )
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    ids = res["ids"][0]

    rows, seen = [], set()
    for i, (doc, meta) in enumerate(zip(docs, metas)):
        norm = normalize_meta(meta or {}, doc)
        key = norm["source"] or (norm["title"], norm["snippet"])
        if key in seen:
            continue
        seen.add(key)

        rows.append(
            {
                "id": ids[i],
                "title": norm["title"],
                "source": norm["source"],
                "snippet": norm["snippet"],
            }
        )
        if len(rows) >= k:
            break
    return rows


@require_GET
def docsearch(request):
    print("docsearch called with query: ", request.GET.get("q"))
    ensure_search_initialized()

    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"results": []})

    k = int(request.GET.get("k", 10))  # 기본 10

    dense_rows = search_dense(q, k)

    print("Dense rows: ", dense_rows[:3])

    return JsonResponse({"results": dense_rows, "meta": {"k": k}})


@login_required
def card_detail(request, card_id):
    card = get_object_or_404(Card, id=card_id, user=request.user)
    messages = ChatMessage.objects.filter(session_id=card.session_id).order_by(
        "created_at"
    )
    context = {
        "card": card,
        "messages": messages,
    }
    return render(request, "my_app/card_detail.html", context)
