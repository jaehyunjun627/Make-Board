<%@ page language="java" contentType="text/html; charset=UTF-8"
   pageEncoding="UTF-8"%>
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core"%>
<%@ taglib prefix="fmt" uri="http://java.sun.com/jsp/jstl/fmt"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<link
   href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
   rel="stylesheet">
<link rel="stylesheet" type="text/css" href="./css/board.css">
<script
   src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<title>BBS List</title>
</head>
<body>
   <c:if test="${msg==0}">
      <script type="text/javascript">
         alert("수정시 비밀번호가 일치하지 않습니다.");
      </script>
   </c:if>

   <c:if test="${msg==1}">
      <script type="text/javascript">
         alert("삭제시 비밀번호가 일치하지 않습니다.");
      </script>
   </c:if>

   <center>
      <div id="list">
         <H2>게시글 보기(전체글: ${count})</H2>
      </div>

      <div id="write">
         <a href="BoardWriteForm.jsp" style="text-decoration: none">글쓰기</a>
      </div>

      <div>
         <table class="table table-striped table-bordered table-hover">
            <thead>

               <tr height="40">
                  <th width="150">번호</th>
                  <th width="500">제목</th>
                  <th width="150">작성자</th>
                  <th width="150">작성일</th>
                  <th width="150">조회</th>
               </tr>
            </thead>
            <!--  ---------------------------------------- -->
            <tbody>
               <c:set var="number" value="${number}" />
               <!-- requestScope.number 값을 pageScope.number 로 복사. 이후 JSP 안에서 마음껏 감소시켜도 request 값은 건드리지 않음 -->
               <!-- 원본(number in request) → 복사본, 복사본(number in page) → 하나씩 줄이면서 사용 -->
               
               
               <!-- inhanced for문 -->
               <c:forEach var="bean" items="${v}">
                  <tr height="40">
                     <td width="50" align="left">${number}</td>
                     <td width="300" align="left">
                     <c:if test="${bean.RE_LEVEL > 1}">
                           <!-- re_level 값에 따라 padding-left 조정 적용 -->
                       <span style="padding-left: ${(bean.RE_STEP-1) * 20}px;"></span>
                     </c:if>
                     <a href="BoardInfoControl.do?num=${bean.NUM}" style='text-decoration: none'> ${bean.SUBJECT}</a></td>

                     <td width="100" align="center">${bean.writer}</td>
                     <td width="150" align="center">${bean.reg_date}</td>
                     <td width="80" align="center">${bean.READCOUNT}</td>
                  </tr>
                  <c:set var="number" value="${number-1}" />
               </c:forEach>
            </tbody>
         </table>
      </div>

      <p />
      <c:if test="${count>0 }">
         <!--  전체글 10개 10/10=1 =>1페이지
        전체글 34개 34/10=3+1 => 4페이지 -->
         <c:set var="pageCount"
            value="${count/pageSize+(count%pageSize==0 ? 0 : 1) }" />
         <!-- 시작 페이지 숫자를 지정  -->
         <c:set var="startPage" value="${1}" />

         <!-- 1~9페이지까지 또는 11 12 13 -->
         <c:if test="${currentPage%10 != 0 }">
            <!-- integerOnly="true" :정수만 출력 -->
            <fmt:parseNumber var="result" value="${currentPage/10 }"
               integerOnly="true" />
            <c:set var="startPage" value="${ result*10+1}" />
         </c:if>
         <!-- 화면에 보여질 페이지 처리 숫자 -->
         <c:set var="pageBlock" value="${10 }" />
         <!--  첫번째 페이지 기준 : 1+10-1=10 -->
         <c:set var="endPage" value="${startPage+pageBlock-1 }" />

         <c:if test="${endPage>pageCount}">
            <c:set var="endPage" value="${pageCount}" />
         </c:if>

         <!-- 이전페이지 -->
         <c:if test="${startPage>10 }">
            <a href="BoardListCon.do?pageNum=${startPage-10 }"
               style="text-decoration: none">[이전]</a>
         </c:if>
         <!-- 페이징 처리 -->
         <c:forEach var="i" begin="${startPage }" end="${endPage }">
            <a href="BoardListCon.do?pageNum=${i}" style="text-decoration: none">[${i}]</a>
         </c:forEach>
         <!-- 다음페이지 -->
         <c:if test="${endPage<pageCount }">
            <a href="BoardListCon.do?pageNum=${startPage+10 }"
               style="text-decoration: none">[다음]</a>
         </c:if>
      </c:if>

   </center>


</body>
</html>